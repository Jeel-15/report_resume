"""
Migration: __documents JSON blob → proper multi-table SQLite schema

Run AFTER creating a backup of app.db:
    python -m db.migrate

Run with --verify-only to just check counts without migrating:
    python -m db.migrate --verify-only
"""
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime

# Add project root to path so we can import schema
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text, inspect
from db.schema import metadata, INDEXES


# ─── CONFIG ───────────────────────────────────────────────────────────────────

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'app.db'
)


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")  # OFF during migration
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def safe_str(v, default=''):
    if v is None:
        return default
    return str(v)


def safe_int(v, default=0):
    try:
        return int(v) if v is not None else default
    except (ValueError, TypeError):
        return default


def safe_float(v, default=0.0):
    try:
        return float(v) if v is not None else default
    except (ValueError, TypeError):
        return default


def safe_json(v, default_val=None):
    """
    Safely serialize a value to JSON string for storage.
    Handles: dict, list, str (already JSON), None.
    """
    if v is None:
        return json.dumps(default_val if default_val is not None else {})
    if isinstance(v, (dict, list)):
        return json.dumps(v)
    if isinstance(v, str):
        try:
            json.loads(v)  # already valid JSON
            return v
        except (json.JSONDecodeError, ValueError):
            return json.dumps(default_val if default_val is not None else {})
    return json.dumps(default_val if default_val is not None else {})


def safe_json_list(v):
    return safe_json(v, default_val=[])


def safe_json_dict(v):
    return safe_json(v, default_val={})


def safe_dt(v):
    """Convert datetime or ISO string to ISO string, or None."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, str) and v.strip():
        return v.strip()
    return None


def read_collection(conn, collection_name):
    """Read all rows from __documents for a given collection."""
    cur = conn.execute(
        "SELECT id, data FROM __documents WHERE collection = ?",
        (collection_name,)
    )
    rows = cur.fetchall()
    result = []
    for row in rows:
        try:
            doc_id = row['id']
            data = json.loads(row['data']) if isinstance(row['data'], str) else row['data']
            result.append((doc_id, data))
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  ⚠ Skipping malformed row in {collection_name} id={row['id']}: {e}")
    return result


def count_collection(conn, collection_name):
    cur = conn.execute(
        "SELECT COUNT(*) FROM __documents WHERE collection = ?",
        (collection_name,)
    )
    return cur.fetchone()[0]


def count_table(conn, table_name):
    try:
        cur = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
        return cur.fetchone()[0]
    except sqlite3.OperationalError:
        return -1  # table doesn't exist yet


# ─── CREATE TABLES ────────────────────────────────────────────────────────────

def create_all_tables():
    engine_url = f"sqlite:///{DB_PATH}"
    engine = create_engine(engine_url, echo=False)
    
    print("\n📦 Creating new tables and indexes...")
    # SQLAlchemy's create_all() can still try to create indexes that already exist
    # when a previous migration attempt partially succeeded. To keep reruns safe,
    # create tables first with indexes temporarily detached, then recreate only the
    # missing indexes explicitly.
    original_indexes = {
        table.name: list(table.indexes)
        for table in metadata.tables.values()
    }
    try:
        for table in metadata.tables.values():
            table.indexes.clear()
        metadata.create_all(engine, checkfirst=True)
    finally:
        for table in metadata.tables.values():
            table.indexes.clear()
            table.indexes.update(original_indexes[table.name])

    def _existing_index_names(conn):
        rows = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='index' AND name IS NOT NULL"
        ).fetchall()
        return {row[0] for row in rows}

    # Create indexes separately and skip ones that already exist.
    with engine.begin() as conn:
        existing_indexes = _existing_index_names(conn)
        for idx in INDEXES:
            if idx.name in existing_indexes:
                continue
            try:
                idx.create(conn, checkfirst=True)
            except Exception:
                pass  # Index may already exist or be unsupported on this SQLite build
    
    print("  ✅ All tables created")


# ─── COLLECTION MIGRATORS ─────────────────────────────────────────────────────

def migrate_degrees(conn, rows):
    for doc_id, d in rows:
        policy = d.get('policy')
        if policy and not isinstance(policy, str):
            policy = json.dumps(policy)
        elif not policy:
            policy = '{}'
        conn.execute("""
            INSERT OR IGNORE INTO degrees
            (id, name, is_active, approval_status, policy, created_by_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_id,
            safe_str(d.get('name')),
            safe_int(d.get('isActive', 1)),
            safe_str(d.get('approvalStatus', 'approved')),
            policy,
            safe_str(d.get('createdBy') or d.get('created_by')) or None,
            safe_dt(d.get('createdAt')),
            safe_dt(d.get('updatedAt')),
        ))


def migrate_departments(conn, rows):
    for doc_id, d in rows:
        degree_id = d.get('degree') or d.get('degree_id') or None
        if isinstance(degree_id, dict):
            degree_id = degree_id.get('$oid') or degree_id.get('id') or None
        conn.execute("""
            INSERT OR IGNORE INTO departments
            (id, name, degree_id, approval_status, rejection_reason, is_active,
             created_by_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_id,
            safe_str(d.get('name')),
            safe_str(degree_id) if degree_id else None,
            safe_str(d.get('approvalStatus', 'approved')),
            safe_str(d.get('rejectionReason', '')),
            safe_int(d.get('isActive', 1)),
            safe_str(d.get('createdBy') or d.get('created_by')) or None,
            safe_dt(d.get('createdAt')),
            safe_dt(d.get('updatedAt')),
        ))


def migrate_majors(conn, rows):
    for doc_id, d in rows:
        degree_id = d.get('degree') or None
        dept_id   = d.get('department') or None
        if isinstance(degree_id, dict):
            degree_id = degree_id.get('$oid') or degree_id.get('id') or None
        if isinstance(dept_id, dict):
            dept_id = dept_id.get('$oid') or dept_id.get('id') or None

        rp = d.get('reportPolicy') or {}
        conn.execute("""
            INSERT OR IGNORE INTO majors
            (id, name, degree_id, department_id, report_language, report_content_type,
             ai_prompt_context, report_policy, report_sections, employment_opportunities,
             is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_id,
            safe_str(d.get('name')),
            safe_str(degree_id) if degree_id else None,
            safe_str(dept_id) if dept_id else None,
            safe_str(d.get('reportLanguage', 'English')),
            safe_str(d.get('reportContentType', 'Text')),
            safe_str(d.get('aiPromptContext', '')),
            safe_json_dict(rp),
            safe_json_list(d.get('reportSections', [])),
            safe_json_list(d.get('employmentOpportunities', [])),
            safe_int(d.get('isActive', 1)),
            safe_dt(d.get('createdAt')),
            safe_dt(d.get('updatedAt')),
        ))


def migrate_universities(conn, rows):
    for doc_id, d in rows:
        conn.execute("""
            INSERT OR IGNORE INTO universities
            (id, name, village_city_name, tehsil, district, state, website, logo,
             approval_status, rejection_reason, is_active, created_by_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_id,
            safe_str(d.get('name')),
            safe_str(d.get('villageCityName', '')),
            safe_str(d.get('tehsil', '')),
            safe_str(d.get('district', '')),
            safe_str(d.get('state', '')),
            safe_str(d.get('website', '')),
            safe_str(d.get('logo', '')),
            safe_str(d.get('approvalStatus', 'approved')),
            safe_str(d.get('rejectionReason', '')),
            safe_int(d.get('isActive', 1)),
            safe_str(d.get('createdBy') or '') or None,
            safe_dt(d.get('createdAt')),
            safe_dt(d.get('updatedAt')),
        ))


def migrate_colleges(conn, rows):
    for doc_id, d in rows:
        uni_id = d.get('university') or None
        if isinstance(uni_id, dict):
            uni_id = uni_id.get('$oid') or uni_id.get('id') or None
        conn.execute("""
            INSERT OR IGNORE INTO colleges
            (id, name, university_id, village_city_name, tehsil, district, state,
             website, logo, approval_status, rejection_reason, is_active, is_verified,
             created_by_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_id,
            safe_str(d.get('name')),
            safe_str(uni_id) if uni_id else None,
            safe_str(d.get('villageCityName', '')),
            safe_str(d.get('tehsil', '')),
            safe_str(d.get('district', '')),
            safe_str(d.get('state', '')),
            safe_str(d.get('website', '')),
            safe_str(d.get('logo', '')),
            safe_str(d.get('approvalStatus', 'approved')),
            safe_str(d.get('rejectionReason', '')),
            safe_int(d.get('isActive', 1)),
            safe_int(d.get('isVerified', 0)),
            safe_str(d.get('createdBy') or '') or None,
            safe_dt(d.get('createdAt')),
            safe_dt(d.get('updatedAt')),
        ))


def migrate_industries(conn, rows):
    for doc_id, d in rows:
        conn.execute("""
            INSERT OR IGNORE INTO industries
            (id, name, industry_type, industry_sub_type, village_city_name, tehsil,
             district, state, website, logo, gst_number, details, key_activities,
             approval_status, rejection_reason, is_active, is_verified,
             created_by_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_id,
            safe_str(d.get('name')),
            safe_str(d.get('industryType', '')),
            safe_str(d.get('industrySubType', '')),
            safe_str(d.get('villageCityName', '')),
            safe_str(d.get('tehsil', '')),
            safe_str(d.get('district', '')),
            safe_str(d.get('state', '')),
            safe_str(d.get('website', '')),
            safe_str(d.get('logo', '')),
            safe_str(d.get('gstNumber', '')),
            safe_str(d.get('details', '')),
            safe_json_list(d.get('keyActivities', [])),
            safe_str(d.get('approvalStatus', 'approved')),
            safe_str(d.get('rejectionReason', '')),
            safe_int(d.get('isActive', 1)),
            safe_int(d.get('isVerified', 0)),
            safe_str(d.get('createdBy') or '') or None,
            safe_dt(d.get('createdAt')),
            safe_dt(d.get('updatedAt')),
        ))


def migrate_users(conn, rows):
    for doc_id, d in rows:
        def _ref(key):
            v = d.get(key)
            if not v:
                return None
            if isinstance(v, dict):
                return safe_str(v.get('$oid') or v.get('id') or '') or None
            return safe_str(v) or None

        conn.execute("""
            INSERT OR IGNORE INTO users
            (id, email, password, role, is_active, name, village_city_name, tehsil,
             district, state, phone, whatsapp, gender, semester, department,
             university_id, college_id, university_logo_override, college_logo_override,
             degree_id, academic_department_id, major_id, roll_number, enrollment_number,
             industry_id, supervisor_name, supervisor_contact, industry_profile_customized,
             industry_village_city_name, industry_tehsil, industry_district, industry_state,
             industry_website, industry_gst_number, industry_details, industry_type,
             industry_sub_type, industry_key_activities, profile_completed,
             email_verified, email_verify_otp_hash, email_verify_otp_exp,
             email_verify_attempts, reset_otp_hash, reset_otp_expires_at,
             reset_otp_attempt_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_id,
            safe_str(d.get('email', '')).lower().strip(),
            safe_str(d.get('password', '')),
            safe_str(d.get('role', 'student')),
            safe_int(d.get('isActive', 1)),
            safe_str(d.get('name', '')),
            safe_str(d.get('villageCityName', '')),
            safe_str(d.get('tehsil', '')),
            safe_str(d.get('district', '')),
            safe_str(d.get('state', '')),
            safe_str(d.get('phone', '')),
            safe_str(d.get('whatsapp', '')),
            safe_str(d.get('gender', '')),
            safe_str(d.get('semester', '')),
            safe_str(d.get('department', '')),
            _ref('university'),
            _ref('college'),
            safe_str(d.get('universityLogoOverride', '')),
            safe_str(d.get('collegeLogoOverride', '')),
            _ref('degree'),
            _ref('academicDepartment'),
            _ref('major'),
            safe_str(d.get('rollNumber', '')),
            safe_str(d.get('enrollmentNumber', '')),
            _ref('industry'),
            safe_str(d.get('supervisorName', '')),
            safe_str(d.get('supervisorContact', '')),
            safe_int(d.get('industryProfileCustomized', 0)),
            safe_str(d.get('industryVillageCityName', '')),
            safe_str(d.get('industryTehsil', '')),
            safe_str(d.get('industryDistrict', '')),
            safe_str(d.get('industryState', '')),
            safe_str(d.get('industryWebsite', '')),
            safe_str(d.get('industryGstNumber', '')),
            safe_str(d.get('industryDetails', '')),
            safe_str(d.get('industryType', '')),
            safe_str(d.get('industrySubType', '')),
            safe_json_list(d.get('industryKeyActivities', [])),
            safe_int(d.get('profileCompleted', 0)),
            safe_int(d.get('emailVerified', 0)),
            d.get('emailVerifyOtpHash') or None,
            safe_dt(d.get('emailVerifyOtpExp')),
            safe_int(d.get('emailVerifyAttempts', 0)),
            d.get('resetOtpHash') or None,
            safe_dt(d.get('resetOtpExpiresAt')),
            safe_int(d.get('resetOtpAttemptCount', 0)),
            safe_dt(d.get('createdAt')),
            safe_dt(d.get('updatedAt')),
        ))


def migrate_reports(conn, rows):
    for doc_id, d in rows:
        def _ref(key):
            v = d.get(key)
            if not v: return None
            if isinstance(v, dict): return safe_str(v.get('$oid') or v.get('id') or '') or None
            return safe_str(v) or None

        conn.execute("""
            INSERT OR IGNORE INTO reports
            (id, user_id, project_title, internship_type, report_academic_year,
             university_id, college_id, degree_id, department_id, major_id, industry_id,
             status, is_paid, generated_content, edited_content, generated_titles,
             section_images, university_snapshot, college_snapshot, industry_snapshot,
             work_keywords, selected_sections, report_config, callback_url,
             error_message, pdf_generated_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_id,
            _ref('user'),
            safe_str(d.get('projectTitle', '')),
            safe_str(d.get('internshipType', '')),
            safe_str(d.get('reportAcademicYear', '')),
            _ref('university'),
            _ref('college'),
            _ref('degree'),
            _ref('department'),
            _ref('major'),
            _ref('industry'),
            safe_str(d.get('status', 'pending')),
            safe_int(d.get('isPaid', 0)),
            safe_json_dict(d.get('generatedContent', {})),
            safe_json_dict(d.get('editedContent', {})),
            safe_json_dict(d.get('generatedTitles', {})),
            safe_json_dict(d.get('sectionImages', {})),
            safe_json_dict(d.get('universitySnapshot', {})),
            safe_json_dict(d.get('collegeSnapshot', {})),
            safe_json_dict(d.get('industrySnapshot', {})),
            safe_json_list(d.get('workKeywords', [])),
            safe_json_list(d.get('selectedSections', [])),
            safe_json_dict(d.get('reportConfig', {})),
            safe_str(d.get('callbackUrl', '')),
            safe_str(d.get('errorMessage', '')),
            safe_dt(d.get('pdfGeneratedAt')),
            safe_dt(d.get('createdAt')),
            safe_dt(d.get('updatedAt')),
        ))


def migrate_work_keywords(conn, rows):
    for doc_id, d in rows:
        major_id = d.get('major') or None
        if isinstance(major_id, dict):
            major_id = major_id.get('$oid') or major_id.get('id') or None
        conn.execute("""
            INSERT OR IGNORE INTO work_keywords
            (id, keyword, industry_type, job_profile, major_id, sort_order, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_id,
            safe_str(d.get('keyword', '')),
            safe_str(d.get('industryType', '')),
            safe_str(d.get('jobProfile', '')),
            safe_str(major_id) if major_id else None,
            safe_int(d.get('sortOrder', 0)),
            safe_int(d.get('isActive', 1)),
            safe_dt(d.get('createdAt')),
            safe_dt(d.get('updatedAt')),
        ))


def migrate_project_titles(conn, rows):
    for doc_id, d in rows:
        major_id  = d.get('major') or None
        degree_id = d.get('degree') or None
        created_by = d.get('createdBy') or None
        for ref in [major_id, degree_id, created_by]:
            if isinstance(ref, dict):
                ref = ref.get('$oid') or ref.get('id') or None
        conn.execute("""
            INSERT OR IGNORE INTO project_titles
            (id, title, major_id, degree_id, is_active, created_by_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_id,
            safe_str(d.get('title', '')),
            safe_str(d.get('major')) if d.get('major') and not isinstance(d.get('major'), dict) else (safe_str(d.get('major', {}).get('$oid') or d.get('major', {}).get('id') or '') or None),
            safe_str(d.get('degree')) if d.get('degree') and not isinstance(d.get('degree'), dict) else (safe_str(d.get('degree', {}).get('$oid') or d.get('degree', {}).get('id') or '') or None),
            safe_int(d.get('isActive', 1)),
            safe_str(d.get('createdBy')) if d.get('createdBy') and not isinstance(d.get('createdBy'), dict) else None,
            safe_dt(d.get('createdAt')),
            safe_dt(d.get('updatedAt')),
        ))


def migrate_resumes(conn, rows):
    for doc_id, d in rows:
        user_id = d.get('user') or None
        if isinstance(user_id, dict):
            user_id = user_id.get('$oid') or user_id.get('id') or None
        conn.execute("""
            INSERT OR IGNORE INTO resumes
            (id, user_id, title, full_name, address, phone, email, photo_url,
             linkedin_url, github_url, career_objective_raw, career_objective_enhanced,
             education, experience, skills, technical_skills, projects, volunteering,
             certifications, languages, coursework, personal_skills,
             status, error_message, download_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_id,
            safe_str(user_id) if user_id else None,
            safe_str(d.get('title', 'Untitled Resume')),
            safe_str(d.get('fullName', '')),
            safe_str(d.get('address', '')),
            safe_str(d.get('phone', '')),
            safe_str(d.get('email', '')),
            safe_str(d.get('photoUrl', '')),
            safe_str(d.get('linkedinUrl', '')),
            safe_str(d.get('githubUrl', '')),
            safe_str(d.get('careerObjectiveRaw', '')),
            safe_str(d.get('careerObjectiveEnhanced', '')),
            safe_json_list(d.get('education', [])),
            safe_json_list(d.get('experience', [])),
            safe_json_list(d.get('skills', [])),
            safe_json_list(d.get('technicalSkills', [])),
            safe_json_list(d.get('projects', [])),
            safe_json_list(d.get('volunteering', [])),
            safe_json_list(d.get('certifications', [])),
            safe_json_list(d.get('languages', [])),
            safe_json_list(d.get('coursework', [])),
            safe_json_list(d.get('personalSkills', [])),
            safe_str(d.get('status', 'draft')),
            safe_str(d.get('errorMessage', '')),
            safe_int(d.get('downloadCount', 0)),
            safe_dt(d.get('createdAt')),
            safe_dt(d.get('updatedAt')),
        ))


def migrate_assignment_sessions(conn, rows):
    for doc_id, d in rows:
        user_id = d.get('user') or None
        if isinstance(user_id, dict):
            user_id = user_id.get('$oid') or user_id.get('id') or None
        conn.execute("""
            INSERT OR IGNORE INTO assignment_sessions
            (id, user_id, title, assignment_type, university_name, degree_name,
             major_name, context_inputs, document_sections, full_content_markdown,
             chat_history, status, error_message, word_count_current, word_count_target,
             generation_count, api_tokens_consumed, is_deleted, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_id,
            safe_str(user_id) if user_id else None,
            safe_str(d.get('title', 'Untitled Assignment')),
            safe_str(d.get('assignmentType', '')),
            safe_str(d.get('universityName', '')),
            safe_str(d.get('degreeName', '')),
            safe_str(d.get('majorName', '')),
            safe_json_dict(d.get('contextInputs', {})),
            safe_json_list(d.get('documentSections', [])),
            safe_str(d.get('fullContentMarkdown', '')),
            safe_json_list(d.get('chatHistory', [])),
            safe_str(d.get('status', 'draft')),
            safe_str(d.get('errorMessage', '')),
            safe_int(d.get('wordCountCurrent', 0)),
            safe_int(d.get('wordCountTarget', 0)),
            safe_int(d.get('generationCount', 0)),
            safe_int(d.get('apiTokensConsumed', 0)),
            safe_int(d.get('isDeleted', 0)),
            safe_dt(d.get('createdAt')),
            safe_dt(d.get('updatedAt')),
        ))


def migrate_assignment_prompts(conn, rows):
    for doc_id, d in rows:
        conn.execute("""
            INSERT OR IGNORE INTO assignment_prompts
            (id, name, assignment_type, trigger_keywords, injected_instruction,
             sort_order, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_id,
            safe_str(d.get('name', '')),
            safe_str(d.get('assignmentType', '*')),
            safe_json_list(d.get('triggerKeywords', [])),
            safe_str(d.get('injectedInstruction', '')),
            safe_int(d.get('sortOrder', 0)),
            safe_int(d.get('isActive', 1)),
            safe_dt(d.get('createdAt')),
            safe_dt(d.get('updatedAt')),
        ))


def migrate_simple(conn, rows, table, col_map):
    """Generic migrator for simple tables with direct field mapping."""
    for doc_id, d in rows:
        values = {'id': doc_id}
        for json_key, col_name in col_map.items():
            v = d.get(json_key)
            if isinstance(v, (dict, list)):
                values[col_name] = json.dumps(v)
            elif v is None:
                values[col_name] = None
            else:
                values[col_name] = str(v) if not isinstance(v, (int, float)) else v
        
        cols   = ', '.join(values.keys())
        params = ', '.join(['?'] * len(values))
        conn.execute(
            f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({params})",
            list(values.values())
        )


# ─── MAIN MIGRATION ───────────────────────────────────────────────────────────

COLLECTIONS = [
    # ORDER MATTERS — migrate referenced tables before referencing tables
    # No FK dependencies:
    'degrees', 'universities', 'services', 'report_content_types',
    'video_guides', 'blog_posts', 'faq_items', 'contact_submissions',
    # Depend on degrees:
    'departments',
    # Depend on universities:
    'colleges',
    # Depend on degrees + departments:
    'majors',
    # Depend on universities + colleges + degrees + departments + majors:
    'industries',
    # Depend on all above:
    'users',
    # Depend on users + all above:
    'reports', 'resumes', 'assignment_sessions',
    # Support tables:
    'work_keywords', 'project_titles',
    'university_report_templates', 'college_report_templates',
    'major_report_templates', 'audit_logs', 'payments',
    'assignment_prompts', 'career_objectives', 'resume_keywords',
]

MIGRATORS = {
    'degrees':                    migrate_degrees,
    'departments':                migrate_departments,
    'majors':                     migrate_majors,
    'universities':               migrate_universities,
    'colleges':                   migrate_colleges,
    'industries':                 migrate_industries,
    'users':                      migrate_users,
    'reports':                    migrate_reports,
    'work_keywords':              migrate_work_keywords,
    'project_titles':             migrate_project_titles,
    'resumes':                    migrate_resumes,
    'assignment_sessions':        migrate_assignment_sessions,
    'assignment_prompts':         migrate_assignment_prompts,
    'career_objectives': lambda c, r: migrate_simple(c, r, 'career_objectives', {
        'text': 'text', 'approvalStatus': 'approval_status',
        'rejectionReason': 'rejection_reason', 'isActive': 'is_active',
        'createdAt': 'created_at', 'updatedAt': 'updated_at',
    }),
    'resume_keywords': lambda c, r: migrate_simple(c, r, 'resume_keywords', {
        'keyword': 'keyword', 'category': 'category',
        'industryType': 'industry_type', 'isActive': 'is_active',
        'sortOrder': 'sort_order', 'createdAt': 'created_at', 'updatedAt': 'updated_at',
    }),
    'contact_submissions': lambda c, r: migrate_simple(c, r, 'contact_submissions', {
        'name': 'name', 'email': 'email', 'phone': 'phone',
        'subject': 'subject', 'message': 'message',
        'status': 'status', 'createdAt': 'created_at',
    }),
    'audit_logs': lambda c, r: migrate_simple(c, r, 'audit_logs', {
        'user': 'user_id', 'action': 'action', 'targetType': 'target_type',
        'targetId': 'target_id', 'detail': 'detail', 'createdAt': 'created_at',
    }),
    'university_report_templates': lambda c, r: migrate_simple(c, r, 'university_report_templates', {
        'university': 'university_id', 'sections': 'sections',
        'isActive': 'is_active', 'useAsDefault': 'use_as_default',
        'description': 'description', 'createdBy': 'created_by_id',
        'createdAt': 'created_at', 'updatedAt': 'updated_at',
    }),
    'college_report_templates': lambda c, r: migrate_simple(c, r, 'college_report_templates', {
        'college': 'college_id', 'university': 'university_id',
        'sections': 'sections', 'useUniversityDefault': 'use_university_default',
        'isActive': 'is_active', 'createdBy': 'created_by_id',
        'createdAt': 'created_at', 'updatedAt': 'updated_at',
    }),
    'major_report_templates': lambda c, r: migrate_simple(c, r, 'major_report_templates', {
        'major': 'major_id', 'college': 'college_id', 'university': 'university_id',
        'sections': 'sections', 'useLevelAboveDefault': 'use_level_above_default',
        'isActive': 'is_active', 'createdBy': 'created_by_id',
        'createdAt': 'created_at', 'updatedAt': 'updated_at',
    }),
    'report_content_types': lambda c, r: migrate_simple(c, r, 'report_content_types', {
        'name': 'name', 'sortOrder': 'sort_order',
        'isActive': 'is_active', 'createdAt': 'created_at', 'updatedAt': 'updated_at',
    }),
    'video_guides': lambda c, r: migrate_simple(c, r, 'video_guides', {
        'title': 'title', 'videoUrl': 'video_url', 'description': 'description',
        'sortOrder': 'sort_order', 'isActive': 'is_active',
        'createdAt': 'created_at', 'updatedAt': 'updated_at',
    }),
    'blog_posts': lambda c, r: migrate_simple(c, r, 'blog_posts', {
        'title': 'title', 'slug': 'slug', 'excerpt': 'excerpt',
        'content': 'content', 'coverImage': 'cover_image', 'tags': 'tags',
        'author': 'author', 'isPublished': 'is_published',
        'publishedAt': 'published_at', 'createdAt': 'created_at', 'updatedAt': 'updated_at',
    }),
    'faq_items': lambda c, r: migrate_simple(c, r, 'faq_items', {
        'question': 'question', 'answer': 'answer', 'category': 'category',
        'sortOrder': 'sort_order', 'isActive': 'is_active',
        'createdAt': 'created_at', 'updatedAt': 'updated_at',
    }),
    'services': lambda c, r: migrate_simple(c, r, 'services', {
        'name': 'name', 'type': 'type', 'price': 'price',
        'gstIncluded': 'gst_included', 'gstPercent': 'gst_percent',
        'freeLimit': 'free_limit', 'description': 'description',
        'isActive': 'is_active', 'degreePricing': 'degree_pricing',
        'createdAt': 'created_at', 'updatedAt': 'updated_at',
    }),
    'payments': lambda c, r: migrate_simple(c, r, 'payments', {
        'user': 'user_id', 'report': 'report_id', 'service': 'service_id',
        'amount': 'amount', 'currency': 'currency', 'status': 'status',
        'paymentMethod': 'payment_method', 'transactionId': 'transaction_id',
        'gatewayData': 'gateway_data', 'createdAt': 'created_at', 'updatedAt': 'updated_at',
    }),
}


def run_migration():
    print("\n" + "="*60)
    print("  ReportGen SQLite Migration")
    print("  JSON blobs → Proper tables")
    print("="*60)

    if not os.path.exists(DB_PATH):
        print(f"\n❌ Database not found: {DB_PATH}")
        sys.exit(1)

    # Step 1: Create tables
    create_all_tables()

    conn = get_conn()

    # Step 2: Snapshot old counts
    print("\n📊 Reading source row counts...")
    source_counts = {}
    for collection in COLLECTIONS:
        source_counts[collection] = count_collection(conn, collection)
        if source_counts[collection] > 0:
            print(f"  {collection:45s} {source_counts[collection]:6d} rows")

    # Step 3: Migrate each collection
    print("\n🔄 Migrating collections...")
    errors = {}

    with conn:
        for collection in COLLECTIONS:
            if source_counts.get(collection, 0) == 0:
                continue

            migrator = MIGRATORS.get(collection)
            if not migrator:
                print(f"  ⚠ No migrator for: {collection} — SKIPPED")
                continue

            rows = read_collection(conn, collection)
            try:
                migrator(conn, rows)
                new_count = count_table(conn, collection)
                src_count = source_counts[collection]
                status = "✅" if new_count == src_count else "⚠"
                print(f"  {status} {collection:45s} {src_count:6d} → {new_count:6d}")
                if new_count != src_count:
                    errors[collection] = (src_count, new_count)
            except Exception as e:
                print(f"  ❌ {collection}: ERROR — {e}")
                errors[collection] = str(e)

    conn.close()

    # Step 4: Report
    print("\n" + "="*60)
    if errors:
        print("⚠️  MIGRATION COMPLETED WITH WARNINGS:")
        for col, detail in errors.items():
            if isinstance(detail, tuple):
                src, new = detail
                print(f"  {col}: expected {src}, got {new} (diff: {new - src})")
            else:
                print(f"  {col}: {detail}")
        print("\nThis may be OK if the diff is due to duplicate data being deduplicated.")
        print("Check the data manually before replacing mongoengine.py")
    else:
        print("✅ MIGRATION SUCCESSFUL — All row counts match!")
        print("\nNext step: Run Phase 4 (replace mongoengine.py)")

    print("="*60 + "\n")


def verify_only():
    """Just check counts — don't migrate."""
    print("\n📊 Verification mode — checking row counts only\n")
    conn = get_conn()

    print(f"{'Collection':45s} {'__documents':12s} {'New table':12s} {'Match':6s}")
    print("-" * 80)

    all_ok = True
    for collection in COLLECTIONS:
        old_count = count_collection(conn, collection)
        new_count = count_table(conn, collection)
        match = "✅" if old_count == new_count else ("➖" if new_count == -1 else "⚠")
        if old_count != new_count and new_count != -1:
            all_ok = False
        print(f"  {collection:45s} {old_count:12d} {new_count:12d} {match}")

    conn.close()
    print()
    if all_ok:
        print("✅ All counts match or tables not yet created")
    else:
        print("⚠️  Some counts don't match — review before proceeding")


if __name__ == '__main__':
    if '--verify-only' in sys.argv:
        verify_only()
    else:
        run_migration()
