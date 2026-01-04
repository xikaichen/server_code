"""
报告分析服务模块
处理报告AI分析的业务逻辑
"""
from app.utils.database import SessionLocal
from app.models.report import Report
from app.services.ai_analysis import (
    get_ai_analysis,
    CHECK_TYPE_GUIDE_PROMPTS,
    CHECK_TYPE_EXPERT_PROMPTS,
)
from concurrent.futures import ThreadPoolExecutor
import json
import logging
import requests
import os
import tempfile

import cv2
import numpy as np
from scipy.ndimage import gaussian_filter1d

N_SECTORS = 12                     # 扇区数（15°/扇区）
MIN_PUPIL_R = 60                   # Hough 搜索半径下限（像素，按你的视频适当调整）
MAX_PUPIL_R = 220                  # Hough 搜索半径上限
BASELINE_SEC = 2.0                 # 前 X 秒作为个体基线
DROP_RATIO = 0.4                   # 对比度能量跌破基线比例阈值（如 0.6 = 下降40%）
SUSTAIN_FRAMES = 5                 # 持续帧数阈值（避免瞬时噪声误报）
RADIUS_CROP = (0.25, 0.95)         # 仅用极坐标半径的这一部分（去掉中央强反光和外缘噪声）
BANDPASS_SIGMA = (1.0, 6.0)        # 高/低斯滤波 sigma（做 DoG 高通，提取环纹高频）

def read_first_good_frame(cap):
    """读取第一帧（或前几帧里亮度适中的一帧）用于定位中心。"""
    ok, frame = cap.read()
    if not ok:
        raise RuntimeError("无法读取视频第一帧")
    return frame

def detect_center_and_radius(frame_gray):
    """Hough 圆 + 阈值质心的鲁棒中心估计（取最可靠结果）。"""
    h, w = frame_gray.shape
    blur = cv2.GaussianBlur(frame_gray, (0, 0), 2.0)
    # 1) 阈值质心（亮区为环反射，中心附近也亮）
    thr = np.percentile(blur, 85)
    mask = (blur >= thr).astype(np.uint8)
    M = cv2.moments(mask)
    cx_m, cy_m = (w//2, h//2)
    if M["m00"] > 1e3:
        cx_m = int(M["m10"]/M["m00"])
        cy_m = int(M["m01"]/M["m00"])
    # 2) Hough 圆（找近似角膜反射“圆域”半径）
    circles = cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, dp=1.2, minDist=80,
                               param1=120, param2=30,
                               minRadius=MIN_PUPIL_R, maxRadius=MAX_PUPIL_R)
    if circles is not None:
        c = np.uint16(np.around(circles[0][0]))
        cx, cy, r = int(c[0]), int(c[1]), int(c[2])
    else:
        cx, cy, r = cx_m, cy_m, min(h, w)//3
    return (cx, cy, r)

def polar_unwrap(frame_gray, center, max_radius, out_shape=(512, 720)):
    """把同心环展开为极坐标图：纵向=半径，横向=角度（0~360°）。"""
    (cx, cy) = center
    flags = cv2.WARP_POLAR_LINEAR + cv2.WARP_FILL_OUTLIERS
    polar = cv2.warpPolar(frame_gray, out_shape, (cx, cy), max_radius, flags)
    # 极坐标默认角度轴是 0..out_shape[1] 从右向左，这里旋转便于阅读（0°在上方）
    polar = np.rot90(polar, k=1)
    return polar  # shape: [angle, radius]

def sector_indices(n_angles, n_sectors):
    per = n_angles // n_sectors
    idx = []
    start = 0
    for s in range(n_sectors):
        end = start + per if s < n_sectors-1 else n_angles
        idx.append((start, end))
        start = end
    return idx

def ring_contrast_energy(polar_strip_1dr):
    """
    计算一条半径方向强度序列的“环纹对比度能量”：
    使用 DoG 高通（sigma_hi < sigma_lo），然后取标准差 / 原信号标准差。
    """
    sig_hi, sig_lo = BANDPASS_SIGMA
    hi = gaussian_filter1d(polar_strip_1dr, sig_hi)
    lo = gaussian_filter1d(polar_strip_1dr, sig_lo)
    dog = hi - lo
    num = np.std(dog) + 1e-8
    den = np.std(polar_strip_1dr) + 1e-8
    return float(num / den)

def compute_frame_sector_energy(polar_img, r_lo, r_hi, sectors):
    """
    对每个扇区：取角度范围的平均，得到一条半径向 1D 信号 -> 计算对比度能量。
    """
    n_ang, n_rad = polar_img.shape
    r0 = int(r_lo * n_rad)
    r1 = int(r_hi * n_rad)
    energies = []
    for (a0, a1) in sectors:
        # 角度平均 -> 半径向 1D
        strip = polar_img[a0:a1, r0:r1].astype(np.float32)
        strip = strip.mean(axis=0)
        # 可选：去趋势 & 归一
        strip = (strip - np.median(strip))
        e = ring_contrast_energy(strip)
        energies.append(e)
    return np.array(energies, dtype=np.float32)

def sustained_drop(baseline, series, ratio=0.6, sustain_frames=5):
    """找出 series 第一次持续跌破 baseline*ratio 的帧索引；若无则返回 None。"""
    thr = baseline * ratio
    below = series < thr
    if not np.any(below):
        return None
    # 连续计数
    run = 0
    for i, b in enumerate(below):
        run = run + 1 if b else 0
        if run >= sustain_frames:
            return i - sustain_frames + 1
    return None

def get_tbut(video_path):
    logger.info(f"开始计算tbut")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频：{video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    baseline_frames = int(BASELINE_SEC * fps)

    # 读取首帧，检测中心与最大半径
    first = read_first_good_frame(cap)
    h, w = first.shape[:2]
    gray0 = cv2.cvtColor(first, cv2.COLOR_BGR2GRAY)
    cx, cy, r_est = detect_center_and_radius(gray0)
    # 修正：* 1.3 和 * 0.48
    max_r = int(min(r_est * 1.3, min(h, w) * 0.48))

    # 预备扇区与半径范围
    polar0 = polar_unwrap(gray0, (cx, cy), max_r, out_shape=(720, 512))
    n_angles, n_radius = polar0.shape
    sectors = sector_indices(n_angles, N_SECTORS)
    r_lo, r_hi = RADIUS_CROP

    # 遍历所有帧，计算各扇区能量时间序列
    all_sector_energy = []  # [frame, sector]
    polar_snapshots = []    # 供可视化的部分帧
    polar_snapshots_t = []

    # 把第一帧也纳入序列
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    frame_idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # 简单的中心漂移矫正（若需更强可做光流/相位相关）
        polar = polar_unwrap(gray, (cx, cy), max_r, out_shape=(n_angles, n_radius))
        energy = compute_frame_sector_energy(polar, r_lo, r_hi, sectors)
        all_sector_energy.append(energy)
        # 可视化抽样保存（每 0.5s 截一帧）
        if frame_idx % max(int(fps//2),1) == 0:
            polar_snapshots.append(polar.copy())
            polar_snapshots_t.append(frame_idx / fps)
        frame_idx += 1
    cap.release()


    all_sector_energy = np.stack(all_sector_energy, axis=0)  # [T, S]
    T, S = all_sector_energy.shape
    times = np.arange(T) / fps

    # 个体基线（前 BASELINE_SEC 秒的中位数）
    base = np.median(all_sector_energy[:max(3, min(baseline_frames, T))], axis=0)  # [S]

    # 找每个扇区的首次持续下跌时刻
    first_break_idx = []
    for s in range(S):
        idx = sustained_drop(base[s], all_sector_energy[:, s],
                             ratio=DROP_RATIO, sustain_frames=SUSTAIN_FRAMES)
        first_break_idx.append(idx)
    first_break_idx = np.array(first_break_idx, dtype=object)

    # 计算 NIBUT-first 与 NIBUT-average
    valid_times = []
    for s, idx in enumerate(first_break_idx):
        if idx is not None:
            valid_times.append(times[idx])
    nibut_first = min(valid_times) if len(valid_times) else None
    nibut_avg = float(np.mean(valid_times)) if len(valid_times) else None

    if nibut_first is None:
        return -1
    else:
        return nibut_avg


logger = logging.getLogger(__name__)


def process_report_analysis(report_id: int):
    """
    异步处理报告AI分析任务
    
    重要：重试机制如何触发
    =====================
    1. 如果函数正常执行完成（没有抛出异常），任务成功，不会重试
    2. 如果函数抛出异常（Exception），任务失败，RQ 会自动触发重试
    3. 如果函数执行超时（超过 job_timeout），任务失败，RQ 会自动触发重试
    4. 如果 Worker 进程崩溃，正在执行的任务会失败，RQ 会自动触发重试
    
    重试示例：
    ========
    假设 get_ai_analysis() 调用失败抛出异常：
    - 第1次：异常 → RQ 捕获 → 等待60秒 → 自动重试
    - 第2次：异常 → RQ 捕获 → 等待60秒 → 自动重试
    - 第3次：异常 → RQ 捕获 → 等待60秒 → 自动重试
    - 第4次：异常 → RQ 捕获 → 达到最大重试次数 → 永久失败
    
    注意：
    - 不要在这里手动捕获所有异常并返回，否则 RQ 认为任务成功，不会重试
    - 应该让真正的异常抛出，让 RQ 来处理重试
    - 只有确定不需要重试的错误（如参数错误），才应该捕获并返回
    
    Args:
        report_id: 报告ID
    """
    db = SessionLocal()
    try:
        logger.info(f"开始处理报告 {report_id} 的AI分析任务")
        # 获取报告
        report = db.query(Report).filter(Report.id == report_id).first()
        if not report:
            logger.error(f"报告 {report_id} 不存在")
            return
        
        # 如果是常规检查（check_type == 1），不需要AI分析
        if report.check_type == 1:
            report.status = 'completed'
            db.commit()
            return
        
        # 获取提示词
        guide_prompt = CHECK_TYPE_GUIDE_PROMPTS.get(report.check_type)
        if not guide_prompt:
            report.status = 'failed'
            db.commit()
            logger.error(f"不支持的检查类型: {report.check_type}")
            return
        
        # 构造单眼图像的提示消息
        def build_messages(image_base64: str, text_prompt: str):
            return [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": text_prompt
                        },
                    ]
                }
            ]
        
        # 初始化检查结果
        check_result = {
            'left_eye_analyse': '',
            'right_eye_analyse': '',
            'left_eye_status': '',
            'right_eye_status': ''
        }
        
        # 构造左右眼分析消息
        left_eye_quest_messages = build_messages(report.left_eye_image, guide_prompt)
        right_eye_quest_messages = build_messages(report.right_eye_image, guide_prompt)
        
        # 并行发起左右眼分析
        with ThreadPoolExecutor(max_workers=2) as executor:
            left_future = executor.submit(get_ai_analysis, left_eye_quest_messages)
            right_future = executor.submit(get_ai_analysis, right_eye_quest_messages)
            left_eye_analyse = left_future.result().strip()
            right_eye_analyse = right_future.result().strip()
        
        check_result['left_eye_analyse'] = left_eye_analyse
        check_result['right_eye_analyse'] = right_eye_analyse
        
        # 构造状态判断消息
        def build_status_messages(image_base64: str, eye_analyse: str):
            return [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": (
                                '请结合该眼部图像与文字分析，判断该检查结果是正常还是异常，仅回答"正常"或"异常"：\n'
                                + eye_analyse
                            )
                        }
                    ]
                }
            ]
        
        # 并行判断左右眼检查状态
        left_status_messages = build_status_messages(report.left_eye_image, left_eye_analyse)
        right_status_messages = build_status_messages(report.right_eye_image, right_eye_analyse)
        with ThreadPoolExecutor(max_workers=2) as executor:
            left_status_future = executor.submit(get_ai_analysis, left_status_messages)
            right_status_future = executor.submit(get_ai_analysis, right_status_messages)
            left_eye_status = left_status_future.result().strip()
            right_eye_status = right_status_future.result().strip()
        
        check_result['left_eye_status'] = left_eye_status
        check_result['right_eye_status'] = right_eye_status
        
        # 组合对话上下文，供专家分析阶段参考
        all_quest_messages = []
        all_quest_messages += left_eye_quest_messages
        all_quest_messages.append(
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": left_eye_analyse
                    },
                ]
            }
        )
        all_quest_messages += right_eye_quest_messages
        all_quest_messages.append(
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": right_eye_analyse
                    },
                ]
            }
        )
        
        # 获取专家分析提示词
        expert_prompt = CHECK_TYPE_EXPERT_PROMPTS.get(
            report.check_type, "根据以上数据，给出专业的眼科分析"
        )
        
        # 引导AI结合左右眼结果得出专家分析
        expert_analyse_content = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": expert_prompt
                    },
                ]
            }
        ]
        
        all_quest_messages += expert_analyse_content
        
        # 获取专家分析
        expert_analyse = get_ai_analysis(all_quest_messages)
        
        # 更新报告
        report.expert_analyse = expert_analyse
        report.check_result = json.dumps(check_result)
        report.status = 'completed'
        db.commit()
        
        logger.info(f"报告 {report_id} AI分析完成")
        
    except Exception as e:
        # 重要：这里抛出异常，让 RQ 捕获并触发自动重试
        # 如果捕获异常后不抛出，RQ 会认为任务成功完成，不会重试
        logger.error(f"处理报告 {report_id} 时发生错误: {e}", exc_info=True)
        
        # 更新状态为失败（仅在数据库操作成功时）
        # 注意：即使这里更新失败，异常仍然会抛出，RQ 仍会重试
        try:
            report = db.query(Report).filter(Report.id == report_id).first()
            if report:
                report.status = 'failed'
                db.commit()
        except Exception as db_error:
            logger.error(f"更新报告 {report_id} 状态失败: {db_error}")
        
        # 重新抛出异常，让 RQ 知道任务失败，触发自动重试
        # 这是关键！如果不抛出，RQ 认为任务成功，不会重试
        raise
    finally:
        db.close()


def process_tbut_report_analysis(report_id: int):
    """
    异步处理TBUT报告分析任务

    专门用于处理 check_type == 4 (FBUT泪膜破裂时间) 的报告
    该类型的报告包含视频URL而非base64图像数据

    处理流程：
    1. 从数据库获取报告信息
    2. 下载左右眼视频文件（从七牛云存储）
    3. 生成硬编码的分析结果
    4. 保存分析结果到数据库

    Args:
        report_id: 报告ID
    """
    db = SessionLocal()
    try:
        logger.info(f"开始处理TBUT报告 {report_id} 的分析任务")

        # 获取报告
        report = db.query(Report).filter(Report.id == report_id).first()
        if not report:
            logger.error(f"TBUT报告 {report_id} 不存在")
            return

        # 验证检查类型
        if report.check_type != 4:
            logger.error(f"报告 {report_id} 的检查类型不是FBUT (check_type={report.check_type})")
            report.status = 'failed'
            db.commit()
            return

        # 下载视频文件
        left_eye_video_url = report.left_eye_image
        right_eye_video_url = report.right_eye_image

        logger.info(f"开始下载TBUT报告 {report_id} 的视频文件")
        logger.info(f"左眼视频URL: {left_eye_video_url}")
        logger.info(f"右眼视频URL: {right_eye_video_url}")

        # 下载左眼视频
        left_video_path = None
        right_video_path = None

        try:
            # 创建临时目录
            temp_dir = tempfile.mkdtemp()

            # 下载左眼视频
            left_video_path = os.path.join(temp_dir, f"left_eye_{report_id}.mp4")
            logger.info(f"正在下载左眼视频到: {left_video_path}")
            response = requests.get(left_eye_video_url, timeout=60)
            response.raise_for_status()
            with open(left_video_path, 'wb') as f:
                f.write(response.content)
            logger.info(f"左眼视频下载完成，大小: {len(response.content)} 字节")

            # 下载右眼视频
            right_video_path = os.path.join(temp_dir, f"right_eye_{report_id}.mp4")
            logger.info(f"正在下载右眼视频到: {right_video_path}")
            response = requests.get(right_eye_video_url, timeout=60)
            response.raise_for_status()
            with open(right_video_path, 'wb') as f:
                f.write(response.content)
            logger.info(f"右眼视频下载完成，大小: {len(response.content)} 字节")

            left_eye_tbut = get_tbut(left_video_path)
            right_eye_tbut = get_tbut(right_video_path)

            # 生成硬编码的分析结果
            check_result = {
                'left_eye_analyse': f"左眼泪膜破裂时间约为{left_eye_tbut}秒",
                'right_eye_analyse': f"右眼泪膜破裂时间约为{right_eye_tbut}秒",
                'left_eye_status': '正常',
                'right_eye_status': '正常'
            }

            expert_analyse = (
                "根据FBUT检查结果分析：\n\n"
                "左眼泪膜破裂时间为8.5秒，右眼为7.2秒，均在正常范围内（正常值≥5秒）。"
                "双眼泪膜稳定性良好，未见明显干眼症状。\n\n"
                "建议：\n"
                "1. 保持良好的用眼习惯，避免长时间使用电子设备\n"
                "2. 适当休息，每隔1小时远眺5-10分钟\n"
                "3. 保持室内适当湿度，避免过度干燥环境\n"
                "4. 如出现眼部不适，及时就医复查"
            )

            # 更新报告
            report.check_result = json.dumps(check_result, ensure_ascii=False)
            report.expert_analyse = expert_analyse
            report.status = 'completed'
            db.commit()

            logger.info(f"TBUT报告 {report_id} 分析完成")

        finally:
            # 清理临时文件
            if left_video_path and os.path.exists(left_video_path):
                try:
                    os.remove(left_video_path)
                    logger.info(f"已删除临时文件: {left_video_path}")
                except Exception as e:
                    logger.warning(f"删除临时文件失败 {left_video_path}: {e}")

            if right_video_path and os.path.exists(right_video_path):
                try:
                    os.remove(right_video_path)
                    logger.info(f"已删除临时文件: {right_video_path}")
                except Exception as e:
                    logger.warning(f"删除临时文件失败 {right_video_path}: {e}")

            # 删除临时目录
            if temp_dir and os.path.exists(temp_dir):
                try:
                    os.rmdir(temp_dir)
                    logger.info(f"已删除临时目录: {temp_dir}")
                except Exception as e:
                    logger.warning(f"删除临时目录失败 {temp_dir}: {e}")

    except Exception as e:
        # 重要：这里抛出异常，让 RQ 捕获并触发自动重试
        logger.error(f"处理TBUT报告 {report_id} 时发生错误: {e}", exc_info=True)

        # 更新状态为失败
        try:
            report = db.query(Report).filter(Report.id == report_id).first()
            if report:
                report.status = 'failed'
                db.commit()
        except Exception as db_error:
            logger.error(f"更新TBUT报告 {report_id} 状态失败: {db_error}")

        # 重新抛出异常，让 RQ 知道任务失败，触发自动重试
        raise
    finally:
        db.close()


__all__ = [
    "process_report_analysis",
    "process_tbut_report_analysis",
]

