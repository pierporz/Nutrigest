CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    birthdate DATE,
    email TEXT,
    phone TEXT,
    fiscal_code TEXT,
    anamnesis TEXT,
    diet TEXT
);

CREATE TABLE IF NOT EXISTS visits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    date DATE,
    notes TEXT,
    weight REAL,
    waist REAL,
    hip REAL,
    height REAL,
    navel REAL,
    custom TEXT,
    FOREIGN KEY (patient_id) REFERENCES patients(id)
);

CREATE TABLE IF NOT EXISTS attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,
    upload_date DATE DEFAULT CURRENT_DATE,
    FOREIGN KEY (patient_id) REFERENCES patients(id)
);

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS foods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    kcal REAL,
    carbs REAL,
    protein REAL,
    fat REAL
);

CREATE TABLE IF NOT EXISTS meal_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    food_id INTEGER NOT NULL,
    grams REAL,
    day TEXT,        -- es: 'Lunedì'
    meal TEXT,       -- es: 'Colazione', 'Pranzo'
    FOREIGN KEY (patient_id) REFERENCES patients(id),
    FOREIGN KEY (food_id) REFERENCES foods(id)
);
CREATE TABLE IF NOT EXISTS obiettivi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    calories INTEGER NOT NULL,
    cho_percent REAL NOT NULL,
    pro_percent REAL NOT NULL,
    fat_percent REAL NOT NULL,
    FOREIGN KEY (patient_id) REFERENCES patients (id)
);
