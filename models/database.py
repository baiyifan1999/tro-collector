import os

import mysql.connector
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")


def get_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
    )


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS cases (
            id INT AUTO_INCREMENT PRIMARY KEY,
            docket_id INT,
            case_name TEXT,
            court VARCHAR(100),
            date_filed VARCHAR(50),
            docket_number VARCHAR(100) UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS defendants (
            id INT AUTO_INCREMENT PRIMARY KEY,
            case_id INT,
            defendant_name TEXT,
            cleaned_name TEXT,
            is_valid TINYINT DEFAULT 1,
            platform VARCHAR(100),
            source_doc_id INT,
            es_synced TINYINT DEFAULT 0,
            FOREIGN KEY (case_id) REFERENCES cases(id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INT AUTO_INCREMENT PRIMARY KEY,
            case_id INT,
            doc_type VARCHAR(50),
            minio_path TEXT,
            source_url TEXT,
            extracted TINYINT DEFAULT 0,
            es_synced TINYINT DEFAULT 0,
            FOREIGN KEY (case_id) REFERENCES cases(id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS risk_scores (
            id INT AUTO_INCREMENT PRIMARY KEY,
            company_name VARCHAR(500) NOT NULL,
            risk_score INT DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uq_company_name (company_name(255))
        )
        """
    )

    conn.commit()
    cursor.close()
    conn.close()


def save_cases(cases_list):
    conn = get_connection()
    cursor = conn.cursor()

    cases_saved = 0
    defendants_saved = 0

    for case in cases_list:
        try:
            cursor.execute(
                """
                INSERT INTO cases (docket_id, case_name, court, date_filed, docket_number)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    case.get("docket_id"),
                    case.get("case_name"),
                    case.get("court"),
                    case.get("date_filed"),
                    case.get("docket_number"),
                ),
            )
        except mysql.connector.IntegrityError:
            conn.rollback()
            continue

        case_id = cursor.lastrowid
        cases_saved += 1

        for defendant_name in case.get("defendants", []):
            cursor.execute(
                """
                INSERT INTO defendants (case_id, defendant_name)
                VALUES (%s, %s)
                """,
                (case_id, defendant_name),
            )
            defendants_saved += 1

        conn.commit()

    cursor.close()
    conn.close()

    print(f"Saved {cases_saved} cases and {defendants_saved} defendants.")
