-- =============================================================================
-- KAVERI STAYS — STAGE 2 AUTHENTICATION SCHEMA
-- =============================================================================

-- 1. Create accounts table
CREATE TABLE IF NOT EXISTS account (
    account_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('guest', 'staff', 'manager', 'owner')),
    property_id INT REFERENCES property(property_id) ON DELETE RESTRICT,
    guest_id INT REFERENCES guest(guest_id) ON DELETE SET NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Role-to-Property Scoping Constraints:
    -- Staff and Managers MUST belong to exactly one property (property_id IS NOT NULL).
    -- Guests and Owners MUST NOT belong to a property (property_id IS NULL).
    CONSTRAINT check_role_property_scope CHECK (
        (role IN ('staff', 'manager') AND property_id IS NOT NULL) OR
        (role IN ('guest', 'owner') AND property_id IS NULL)
    )
);

-- 2. Create refresh_token table
CREATE TABLE IF NOT EXISTS refresh_token (
    token_id SERIAL PRIMARY KEY,
    account_id INT NOT NULL REFERENCES account(account_id) ON DELETE CASCADE,
    token_hash VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    replaced_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for authentication performance
CREATE INDEX IF NOT EXISTS idx_account_email ON account(email);
CREATE INDEX IF NOT EXISTS idx_account_role ON account(role);
CREATE INDEX IF NOT EXISTS idx_refresh_token_hash ON refresh_token(token_hash);
CREATE INDEX IF NOT EXISTS idx_refresh_token_account ON refresh_token(account_id);

-- 3. Seed initial role accounts (all default to password: 'Password123!')
-- Hash: $2b$12$kwG0eRCdjm6tEHD6DDYyB../ONVQssyJUtg3wgw7tImDFQPKbnnK6
INSERT INTO account (name, email, password_hash, role, property_id, guest_id)
VALUES
    -- Global Owner
    ('Kaveri Owner', 'owner@kaveristays.com', '$2b$12$kwG0eRCdjm6tEHD6DDYyB../ONVQssyJUtg3wgw7tImDFQPKbnnK6', 'owner', NULL, NULL),

    -- Property Managers
    ('Coorg Manager', 'manager.coorg@kaveristays.com', '$2b$12$kwG0eRCdjm6tEHD6DDYyB../ONVQssyJUtg3wgw7tImDFQPKbnnK6', 'manager', 1, NULL),
    ('Ooty Manager', 'manager.ooty@kaveristays.com', '$2b$12$kwG0eRCdjm6tEHD6DDYyB../ONVQssyJUtg3wgw7tImDFQPKbnnK6', 'manager', 2, NULL),
    ('Alleppey Manager', 'manager.alleppey@kaveristays.com', '$2b$12$kwG0eRCdjm6tEHD6DDYyB../ONVQssyJUtg3wgw7tImDFQPKbnnK6', 'manager', 3, NULL),

    -- Property Staff
    ('Coorg Front Desk', 'staff.coorg@kaveristays.com', '$2b$12$kwG0eRCdjm6tEHD6DDYyB../ONVQssyJUtg3wgw7tImDFQPKbnnK6', 'staff', 1, NULL),
    ('Ooty Front Desk', 'staff.ooty@kaveristays.com', '$2b$12$kwG0eRCdjm6tEHD6DDYyB../ONVQssyJUtg3wgw7tImDFQPKbnnK6', 'staff', 2, NULL),
    ('Alleppey Front Desk', 'staff.alleppey@kaveristays.com', '$2b$12$kwG0eRCdjm6tEHD6DDYyB../ONVQssyJUtg3wgw7tImDFQPKbnnK6', 'staff', 3, NULL),

    -- Registered Guests (linked to existing guest table entries)
    ('Aarav Sharma', 'aarav.sharma@example.com', '$2b$12$kwG0eRCdjm6tEHD6DDYyB../ONVQssyJUtg3wgw7tImDFQPKbnnK6', 'guest', NULL, 1),
    ('Anita Desai', 'anita.desai@example.com', '$2b$12$kwG0eRCdjm6tEHD6DDYyB../ONVQssyJUtg3wgw7tImDFQPKbnnK6', 'guest', NULL, 2),
    ('Demo Guest', 'guest@example.com', '$2b$12$kwG0eRCdjm6tEHD6DDYyB../ONVQssyJUtg3wgw7tImDFQPKbnnK6', 'guest', NULL, NULL)
ON CONFLICT (email) DO NOTHING;
