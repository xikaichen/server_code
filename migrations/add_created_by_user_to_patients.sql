-- Migration: Add created_by_user field to patients table
-- Date: 2026-01-06
-- Description: Add user ownership tracking to patient records
-- 
-- This migration adds a new column 'created_by_user' to track which user created each patient.
-- The field references the 'uid' field from the 'users' table (not the auto-increment 'id').

-- ============================================================================
-- STEP 1: Add the new column (nullable initially for existing records)
-- ============================================================================

ALTER TABLE patients 
ADD COLUMN created_by_user INT NULL COMMENT '创建患者的用户UID';

-- ============================================================================
-- STEP 2: Add index for performance (filtering by created_by_user will be common)
-- ============================================================================

CREATE INDEX idx_patients_created_by_user ON patients(created_by_user);

-- ============================================================================
-- STEP 3: Update existing records
-- ============================================================================

-- IMPORTANT: You need to decide how to handle existing patient records.
-- Option A: Assign all existing patients to a specific user (e.g., admin user with uid=1)
-- Option B: Delete all existing patients (if this is a development environment)
-- Option C: Keep them as NULL and handle in application logic

-- Option A: Assign to a default user (RECOMMENDED for production)
-- Replace '1' with the actual UID of the user who should own existing patients
-- UPDATE patients SET created_by_user = 1 WHERE created_by_user IS NULL;

-- Option B: Delete existing patients (ONLY for development/testing)
-- DELETE FROM patients WHERE created_by_user IS NULL;

-- Option C: Keep as NULL (NOT RECOMMENDED - will cause issues with NOT NULL constraint)
-- Do nothing here, but you'll need to handle NULL values in your application

-- ============================================================================
-- STEP 4: Make the column NOT NULL (after updating existing records)
-- ============================================================================

-- IMPORTANT: Only run this after you've updated existing records in STEP 3!
-- Uncomment the line below after choosing and executing one of the options above:

-- ALTER TABLE patients MODIFY COLUMN created_by_user INT NOT NULL COMMENT '创建患者的用户UID';

-- ============================================================================
-- STEP 5: Add foreign key constraint (OPTIONAL but RECOMMENDED)
-- ============================================================================

-- This ensures referential integrity between patients and users tables
-- Note: This references the 'uid' column in users table, not the 'id' column

-- IMPORTANT: Only add this constraint if:
-- 1. All existing patients have been assigned a valid user UID
-- 2. You want to prevent deletion of users who have created patients
-- 3. Or you want to set up CASCADE delete (see alternative below)

-- Option A: Prevent user deletion if they have patients (RESTRICT)
-- ALTER TABLE patients 
-- ADD CONSTRAINT fk_patients_created_by_user 
-- FOREIGN KEY (created_by_user) REFERENCES users(uid) 
-- ON DELETE RESTRICT 
-- ON UPDATE CASCADE;

-- Option B: Delete patients when user is deleted (CASCADE) - USE WITH CAUTION!
-- ALTER TABLE patients 
-- ADD CONSTRAINT fk_patients_created_by_user 
-- FOREIGN KEY (created_by_user) REFERENCES users(uid) 
-- ON DELETE CASCADE 
-- ON UPDATE CASCADE;

-- Option C: Set to NULL when user is deleted (SET NULL) - Requires column to be nullable
-- ALTER TABLE patients 
-- ADD CONSTRAINT fk_patients_created_by_user 
-- FOREIGN KEY (created_by_user) REFERENCES users(uid) 
-- ON DELETE SET NULL 
-- ON UPDATE CASCADE;

-- ============================================================================
-- ROLLBACK SCRIPT (in case you need to undo this migration)
-- ============================================================================

-- To rollback this migration, run the following commands:
-- 
-- -- Remove foreign key constraint (if added)
-- -- ALTER TABLE patients DROP FOREIGN KEY fk_patients_created_by_user;
-- 
-- -- Remove index
-- -- DROP INDEX idx_patients_created_by_user ON patients;
-- 
-- -- Remove column
-- -- ALTER TABLE patients DROP COLUMN created_by_user;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Check the table structure
-- DESCRIBE patients;

-- Check existing data
-- SELECT id, name, created_by_user, created_at FROM patients LIMIT 10;

-- Count patients by creator
-- SELECT created_by_user, COUNT(*) as patient_count 
-- FROM patients 
-- GROUP BY created_by_user;

-- Find patients without a creator (should be 0 after migration)
-- SELECT COUNT(*) FROM patients WHERE created_by_user IS NULL;

