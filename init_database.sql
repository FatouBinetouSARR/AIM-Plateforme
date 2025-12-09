-- init_database.sql
-- 1. Table utilisateurs
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK(role IN ('admin', 'marketing', 'analyst')),
    department VARCHAR(50),
    status VARCHAR(10) DEFAULT 'active' CHECK(status IN ('active', 'inactive')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    avatar_color VARCHAR(20)
);

-- 2. Table avis
CREATE TABLE IF NOT EXISTS reviews (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    product_name VARCHAR(200),
    review_text TEXT NOT NULL,
    rating INTEGER CHECK(rating >= 1 AND rating <= 5),
    sentiment VARCHAR(10) CHECK(sentiment IN ('positive', 'negative', 'neutral')),
    category VARCHAR(50),
    is_fake BOOLEAN DEFAULT FALSE,
    detection_confidence FLOAT,
    source VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    analyzed_at TIMESTAMP,
    confidence_reason TEXT
);

-- 3. Table activités
CREATE TABLE IF NOT EXISTS activities (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    activity_type VARCHAR(50) NOT NULL,
    description TEXT,
    ip_address VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Table analyses
CREATE TABLE IF NOT EXISTS analyses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    analysis_type VARCHAR(50) NOT NULL,
    parameters TEXT,
    result TEXT,
    status VARCHAR(20) CHECK(status IN ('pending', 'processing', 'completed', 'failed')),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    execution_time FLOAT
);

-- 5. Créer l'utilisateur admin par défaut (mot de passe: Passer123)
-- Le mot de passe hashé pour 'Passer123' est: 6b3a55e0261b0304143f805a24924d0c1c44524821305f31d9277843b8a10f4e
INSERT INTO users (username, email, password, full_name, role, avatar_color) 
VALUES (
    'admin',
    'admin@aim.com',
    '6b3a55e0261b0304143f805a24924d0c1c44524821305f31d9277843b8a10f4e',
    'Administrateur Principal',
    'admin',
    '#FF5630'
) ON CONFLICT (username) DO NOTHING;

-- 6. Créer des index pour la performance
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_reviews_sentiment ON reviews(sentiment);
CREATE INDEX IF NOT EXISTS idx_reviews_fake ON reviews(is_fake);
CREATE INDEX IF NOT EXISTS idx_reviews_user ON reviews(user_id);
CREATE INDEX IF NOT EXISTS idx_activities_user ON activities(user_id);
CREATE INDEX IF NOT EXISTS idx_activities_type ON activities(activity_type);
CREATE INDEX IF NOT EXISTS idx_analyses_user ON analyses(user_id);
CREATE INDEX IF NOT EXISTS idx_analyses_status ON analyses(status);

-- 7. Vérifier les tables créées
\dt

-- 8. Vérifier l'utilisateur admin
SELECT id, username, email, role, status FROM users WHERE username = 'admin';