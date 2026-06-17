from flask import Flask, render_template, redirect, url_for, flash, request, session, Response, jsonify, current_app
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import time
from datetime import datetime, timedelta
from io import StringIO
import os
import csv
import socket
import logging
from app.config import Config

from app.forms import RegistrationForm, LoginForm, CSVUploadForm, AddressLookupForm, DataSourceForm
from app.geocoding import create_geocoding_service
from app.lime_survey import limesurvey_service
import math
from dateutil.relativedelta import relativedelta
from app.audit_logger import (
    setup_audit_logger,
    log_login,
    log_logout,
    log_data_fetch,
    log_data_export,
    log_csv_upload,
    log_manual_lookup
)

# Configure logging
logger = logging.getLogger(__name__)

# Initialize SQLAlchemy
db = SQLAlchemy()

# Store results outside of session (to avoid session size limits)
user_results = {}


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize audit logging
    audit_logger = setup_audit_logger(app)
    app.audit_logger = audit_logger

    # Init DB and Login
    db.init_app(app)
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    login_manager.login_message_category = 'info'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Create upload folder
    upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)

    # Initialize geocoding service
    base_url = app.config.get('NYC_GEOCLIENT_URL', 'https://api.nyc.gov/geo/geoclient/v2')
    
    app.logger.info(f"NYC_GEOCLIENT_URL set to: {app.config.get('NYC_GEOCLIENT_URL')}")
    if not app.config.get('NYC_GEOCLIENT_APP_ID') or not app.config.get('NYC_GEOCLIENT_APP_KEY'):
        app.logger.warning("NYC Geoclient credentials are missing. API geocoding will be skipped.")

    # Resolve NTA mapping file path (relative to app.root_path if not absolute)
    nta_file_cfg = app.config.get('NTA_MAPPING_FILE', 'zip_to_nta_mapping.csv')
    nta_file = nta_file_cfg
    if not os.path.isabs(nta_file):
        nta_file = os.path.join(app.root_path, nta_file_cfg)

    # Create the geocoding service and attach to app
    app.geocoding_service = create_geocoding_service(base_url=base_url)

    # Load NTA mapping if file exists
    if os.path.exists(nta_file):
        loaded = app.geocoding_service.load_nta_mapping(nta_file)
        if not loaded:
            app.logger.warning(f"Failed to load NTA mapping from {nta_file}")
    else:
        app.logger.warning(f"NTA mapping file not found: {nta_file}")

    # Ensure database tables exist
    with app.app_context():
        db.create_all()

    # Close the geocoding HTTP session cleanly on app teardown
    @app.teardown_appcontext
    def close_geocoding_service(exception=None):
        svc = getattr(app, 'geocoding_service', None)
        if svc:
            try:
                svc.close()
                app.logger.debug("Geocoding service session closed")
            except Exception as e:
                app.logger.debug(f"Error closing geocoding service session: {e}")

    # ==================== HELPER FUNCTIONS ====================

    def get_user_results():
        """Get results for current user."""
        if current_user.is_authenticated:
            return user_results.get(current_user.id, [])
        return []

    def set_user_results(results):
        """Store results for current user."""
        if current_user.is_authenticated:
            user_results[current_user.id] = results

    def clear_user_results():
        """Clear results for current user."""
        if current_user.is_authenticated and current_user.id in user_results:
            del user_results[current_user.id]

    def parse_limesurvey_record(record):
        """
        Handle both normalized LimeSurvey records (already mapped to first_name etc.)
        and raw API records with Q001..Q013 fields.
        """
        # Case 1: Already normalized (as lime_survey.py shows)
        if any(k in record for k in ('first_name', 'address_1', 'city', 'zip_code')):
            return {
                'response_id': str(record.get('response_id') or record.get('id') or record.get('record_id') or '').strip(),
                'record_id': str(record.get('record_id') or record.get('response_id') or record.get('id') or '').strip(),
                'date': (record.get('date') or '').strip(),
                'first_name': (record.get('first_name') or '').strip(),
                'last_name': (record.get('last_name') or '').strip(),
                'address_1': (record.get('address_1') or '').strip(),
                'address_2': (record.get('address_2') or '').strip(),
                'city': (record.get('city') or '').strip(),
                'state': (record.get('state') or '').strip(),
                'zip_code': (record.get('zip_code') or '').strip(),
                'gender': (record.get('gender') or '').strip(),
                'preferred_language': (record.get('preferred_language') or '').strip(),
                'preferred_time': (record.get('preferred_time') or '').strip(),
                'placement_exam': (record.get('placement_exam') or '').strip(),
                'enrollment_complete': (record.get('enrollment_complete') or '').strip(),
            }
        # Case 2: Raw API payload with Q-codes
        return {
            'response_id': str(record.get('id', '')).strip(),
            'record_id': str(record.get('id', '')).strip(),
            'date': (record.get('Q001') or '').strip(),
            'first_name': (record.get('Q002') or '').strip(),
            'last_name': (record.get('Q003') or '').strip(),
            'address_1': (record.get('Q004') or '').strip(),
            'address_2': (record.get('Q005') or '').strip(),
            'city': (record.get('Q006') or '').strip(),
            'state': (record.get('Q007') or '').strip(),
            'zip_code': (record.get('Q008') or '').strip(),
            'gender': (record.get('Q009') or '').strip(),
            'preferred_language': (record.get('Q010') or '').strip(),
            'preferred_time': (record.get('Q011') or '').strip(),
            'placement_exam': (record.get('Q012') or '').strip(),
            'enrollment_complete': (record.get('Q013') or '').strip(),
        }

    def normalize_csv_row(row):
        """
        Normalize a single CSV row from LimeSurvey or REDCap to the standard schema:
        record_id, date, first_name, last_name, address_1, address_2, city, state, zip_code.
        Detects by headers and is tolerant to casing differences.
        """
        lower_map = {k.lower(): k for k in row.keys() if isinstance(k, str)}

        def g(*names):
            for name in names:
                if not isinstance(name, str):
                    continue
                k = lower_map.get(name.lower())
                if k is not None:
                    return row.get(k, '')
            return ''

        # Detect likely source
        has_ls = g('Response ID', 'ZIP Code') != '' or ('response id' in lower_map) or ('zip code' in lower_map)
        has_rc = ('record_id' in lower_map) or ('abe_zip' in lower_map)

        if has_ls:
            return {
                'record_id': str(g('Response ID', 'id')).strip(),
                'date': g('Date'),
                'first_name': g('First Name'),
                'last_name': g('Last Name'),
                'address_1': g('Address'),
                'address_2': g('Address_2'),
                'city': g('City'),
                'state': g('State'),
                'zip_code': g('ZIP Code'),
            }
        if has_rc:
            return {
                'record_id': str(g('record_id')).strip(),
                'date': g('date', 'aded_selfref_date'),
                'first_name': g('aded_selfref_firstname', 'first_name', 'fname', 'first'),
                'last_name': g('aded_selfref_lastname', 'last_name', 'lname', 'last'),
                'address_1': g('abe_address', 'address', 'street'),
                'address_2': g('abe_address_2', 'address_2', 'street2'),
                'city': g('abe_city', 'city'),
                'state': g('abe_state', 'state'),
                'zip_code': g('abe_zip', 'zip', 'ZIP'),
            }

        # Fallback: best-effort mapping
        return {
            'record_id': str(g('record_id', 'Response ID', 'id')).strip(),
            'date': g('date', 'Date'),
            'first_name': g('first_name', 'First Name'),
            'last_name': g('last_name', 'Last Name'),
            'address_1': g('abe_address', 'Address', 'address', 'street'),
            'address_2': g('abe_address_2', 'Address_2', 'address_2', 'street2'),
            'city': g('abe_city', 'City', 'city'),
            'state': g('abe_state', 'State', 'state'),
            'zip_code': g('abe_zip', 'ZIP Code', 'zip', 'ZIP'),
        }

    def process_records(records, source_type='csv'):
        """Process records and assign NTAs."""
        def safe_str(value):
            """Convert value to string, handling None and NaN without pandas."""
            if value is None:
                return ''
            try:
                if isinstance(value, float) and math.isnan(value):
                    return ''
            except (TypeError, ValueError):
                pass
            return str(value).strip()

        results = []
        start_time = time.time()
        app.logger.info("\n" + "=" * 60)
        app.logger.info(f"PROCESSING {len(records)} RECORDS FROM {source_type.upper()}")
        app.logger.info("=" * 60)

        for i, record in enumerate(records):
            # Parse record based on source type
            if source_type == 'limesurvey':
                parsed_record = parse_limesurvey_record(record)
            else:
                parsed_record = record

            # Extract fields
            record_id = safe_str(parsed_record.get('record_id', f'{source_type}_{i+1}'))
            date = safe_str(parsed_record.get('date', ''))
            first_name = safe_str(parsed_record.get('first_name', ''))
            last_name = safe_str(parsed_record.get('last_name', ''))
            address_1 = safe_str(parsed_record.get('address_1', ''))
            address_2 = safe_str(parsed_record.get('address_2', ''))
            city = safe_str(parsed_record.get('city', ''))
            state = safe_str(parsed_record.get('state', ''))
            zip_code = safe_str(parsed_record.get('zip_code', ''))

            # Skip empty records
            if not first_name and not last_name and not address_1:
                app.logger.debug(f"  Skipping empty record {i+1} (ID: {record_id})")
                continue

            address_parts = [address_1, address_2, city, state, zip_code]
            full_address = ', '.join(part for part in address_parts if part)
            full_name = ' '.join(part for part in [first_name, last_name] if part)

            # Get NTA using the service attached to the app
            nta_result = app.geocoding_service.assign_nta(
                address_1,
                city,
                state,
                zip_code,
                app_id=app.config.get('NYC_GEOCLIENT_APP_ID'),
                app_key=app.config.get('NYC_GEOCLIENT_APP_KEY')
            )

            app.logger.debug(f"  Record {i+1} (ID: {record_id}): {first_name} {last_name}, ZIP={zip_code}")
            app.logger.debug(f"    -> nta_code: '{nta_result.get('nta_code')}'")
            app.logger.debug(f"    -> nta_name: '{nta_result.get('nta_name')}'")

            result = {
                'record_id': record_id,
                'date': date,
                'first_name': first_name,
                'last_name': last_name,
                'full_name': full_name,
                'full_address': full_address,
                'zip_code': zip_code,
                'nta_code': nta_result.get('nta_code', 'Unknown'),
                'nta_name': nta_result.get('nta_name', 'Unknown'),
                'latitude': nta_result.get('latitude'),
                'longitude': nta_result.get('longitude'),
                'source': nta_result.get('source', 'unknown'),
                'data_source': source_type
            }
            results.append(result)

        # Summary
        end_time = time.time()
        elapsed = end_time - start_time
        app.logger.info("=" * 60)
        app.logger.info(f"COMPLETE: {len(results)} records in {elapsed:.2f} seconds")
        if results:
            app.logger.info("\nFIRST RESULT DETAILS:")
            for key, value in results[0].items():
                app.logger.info(f"  {key}: '{value}'")
        app.logger.info("=" * 60 + "\n")

        return results

    def format_timing(timing_details, record_count):
        """
        Format timing details into a human-readable summary.
        """
        def format_duration(seconds):
            """Convert seconds to readable format."""
            if seconds < 1:
                return f"{seconds * 1000:.0f} ms"
            elif seconds < 60:
                return f"{seconds:.1f} sec"
            elif seconds < 3600:
                minutes = int(seconds // 60)
                secs = seconds % 60
                return f"{minutes} min {secs:.0f} sec"
            else:
                hours = int(seconds // 3600)
                minutes = int((seconds % 3600) // 60)
                return f"{hours} hr {minutes} min"

        summary = {
            'total': format_duration(timing_details.get('total_time', 0)),
            'fetch': format_duration(timing_details.get('fetch_time', 0)),
            'process': format_duration(timing_details.get('process_time', 0)),
            'per_record': format_duration(timing_details.get('per_record_time', 0)),
            'record_count': record_count,
            'records_per_second': record_count / timing_details.get('total_time', 1) if timing_details.get('total_time', 0) > 0 else 0
        }
        return summary

    # ==================== ROUTES ====================

    @app.route('/')
    @login_required
    def index():
        limesurvey_configured = bool(
            app.config.get('LIMESURVEY_URL') and
            app.config.get('LIMESURVEY_USERNAME') and
            app.config.get('LIMESURVEY_PASSWORD') and
            app.config.get('LIMESURVEY_SURVEY_ID')
        )
        nta_loaded = app.geocoding_service.nta_mapping_loaded
        return render_template('index.html',
                               user=current_user,
                               limesurvey_configured=limesurvey_configured,
                               nta_loaded=nta_loaded)

    @app.route('/select-source')
    @login_required
    def select_source():
        """Page to select data source"""
        limesurvey_api_configured = bool(
            app.config.get('LIMESURVEY_URL') and
            app.config.get('LIMESURVEY_USERNAME') and
            app.config.get('LIMESURVEY_PASSWORD') and
            app.config.get('LIMESURVEY_SURVEY_ID')
        )
        return render_template(
            'select_source.html',
            limesurvey_api_configured=limesurvey_api_configured
        )

    @app.route('/fetch-limesurvey', methods=['GET', 'POST'])
    @login_required
    def fetch_from_limesurvey():
        """Fetch data from LimeSurvey API with date filtering"""
        form = DataSourceForm()
        if request.method == 'GET':
            return render_template('fetch_limesurvey.html', form=form)

        if form.validate_on_submit():
            clear_user_results()
            # Start timing
            total_start_time = time.time()
            timing_details = {}

            # Calculate date range based on filter type
            start_date = None
            end_date = None
            today = datetime.now().date()
            date_filter_type = form.date_filter_type.data

            if date_filter_type == 'preset':
                preset = form.preset_range.data
                if preset == '7days':
                    start_date = today - timedelta(days=7)
                    end_date = today
                elif preset == '30days':
                    start_date = today - timedelta(days=30)
                    end_date = today
                elif preset == '90days':
                    start_date = today - timedelta(days=90)
                    end_date = today
                elif preset == 'thismonth':
                    start_date = today.replace(day=1)
                    end_date = today
                elif preset == 'lastmonth':
                    first_of_this_month = today.replace(day=1)
                    end_date = first_of_this_month - timedelta(days=1)
                    start_date = end_date.replace(day=1)
                elif preset == 'thisyear':
                    start_date = today.replace(month=1, day=1)
                    end_date = today
                elif preset == 'lastyear':
                    start_date = today.replace(year=today.year - 1, month=1, day=1)
                    end_date = today.replace(year=today.year - 1, month=12, day=31)
            elif date_filter_type == 'custom':
                start_date = form.start_date.data
                end_date = form.end_date.data

            # Build date range string for display
            if start_date or end_date:
                date_range_str = f"{start_date or 'beginning'} to {end_date or 'now'}"
            else:
                date_range_str = "all dates"

            # Fetch records from LimeSurvey
            fetch_start_time = time.time()
            records, error = limesurvey_service.fetch_from_api()
            timing_details['fetch_time'] = time.time() - fetch_start_time

            if error:
                flash(f'Error fetching from LimeSurvey: {error}', 'danger')
                return redirect(url_for('select_source'))

            if not records:
                flash('No records found in LimeSurvey.', 'warning')
                return redirect(url_for('select_source'))

            # Filter records by date if needed
            if start_date or end_date:
                filtered_records = []
                for record in records:
                    parsed = parse_limesurvey_record(record)
                    record_date_str = parsed.get('date', '').strip()
                    if not record_date_str:
                        continue

                    record_date = None
                    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%Y-%m-%d %H:%M:%S'):
                        try:
                            record_date = datetime.strptime(record_date_str, fmt).date()
                            break
                        except ValueError:
                            continue

                    if not record_date:
                        continue

                    if start_date and record_date < start_date:
                        continue
                    if end_date and record_date > end_date:
                        continue

                    filtered_records.append(record)

                records = filtered_records

            if not records:
                flash(f'No records found for date range: {date_range_str}', 'warning')
                return redirect(url_for('select_source'))

            # Process records
            process_start_time = time.time()
            results = process_records(records, source_type='limesurvey')
            timing_details['process_time'] = time.time() - process_start_time
            timing_details['total_time'] = time.time() - total_start_time
            timing_details['per_record_time'] = (
                timing_details['total_time'] / len(results)
                if results else 0
            )

            if not results:
                flash('No valid records to process.', 'warning')
                return redirect(url_for('select_source'))

            set_user_results(results)
            session['last_processing_seconds'] = timing_details['total_time']
            session['last_date_range'] = date_range_str
            session['last_timing_details'] = format_timing(timing_details, len(results))

            # LOG THE FETCH
            log_data_fetch(
                survey_key=app.config.get('LIMESURVEY_SURVEY_ID', 'unknown'),
                survey_name='LimeSurvey',
                record_count=len(results),
                date_range=date_range_str,
                success=True
            )

            flash(
                f'Successfully processed {len(results)} LimeSurvey records for {date_range_str}.',
                'success'
            )
            return redirect(url_for('show_results'))

        return render_template('fetch_limesurvey.html', form=form)

    @app.route('/limesurvey/test')
    @login_required
    def test_limesurvey_connection():
        """Test LimeSurvey API connection"""
        surveys, error = limesurvey_service.list_surveys()
        if error:
            return jsonify({
                'status': 'error',
                'message': error
            }), 500
        return jsonify({
            'status': 'success',
            'message': 'Connected to LimeSurvey successfully',
            'surveys': surveys
        })

    @app.route('/upload-csv', methods=['GET', 'POST'])
    @login_required
    def upload_csv():
        form = CSVUploadForm()
        # Clear old results
        clear_user_results()

        if form.validate_on_submit():
            # Start timing
            start_time = time.time()
            file = form.csv_file.data
            filename = file.filename

            # Save file
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            try:
                # Read and normalize CSV rows
                records = []
                with open(filepath, 'r', encoding='utf-8-sig', newline='') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        records.append(normalize_csv_row(row))

                # Clean up file
                if os.path.exists(filepath):
                    os.remove(filepath)

                if not records:
                    flash('No records found in CSV file.', 'warning')
                    return redirect(url_for('upload_csv'))

                # Process normalized records
                results = process_records(records, source_type='csv')
                log_csv_upload(filename=filename, record_count=len(results), success=True)

                # Calculate processing time
                end_time = time.time()
                processing_time = end_time - start_time

                # Store results for this user
                set_user_results(results)

                # Store processing time in session
                session['last_processing_seconds'] = processing_time

                # Format time message
                if processing_time < 1:
                    time_msg = f"{processing_time * 1000:.0f} milliseconds"
                else:
                    time_msg = f"{processing_time:.2f} seconds"

                flash(f'Successfully processed {len(results)} records from CSV in {time_msg}.', 'success')
                return redirect(url_for('show_results'))

            except Exception as e:
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                    except:
                        pass
                app.logger.error(f"Error processing CSV file: {str(e)}", exc_info=True)
                flash(f'Error processing file: {str(e)}', 'danger')
                return redirect(url_for('upload_csv'))

        return render_template('upload_csv.html', form=form)

    @app.route('/manual-lookup', methods=['GET', 'POST'])
    @login_required
    def manual_lookup():
        form = AddressLookupForm()
        result = None

        if form.validate_on_submit():
            address_parts = [form.address_line_1.data]
            if form.address_line_2.data:
                address_parts.append(form.address_line_2.data)
            address_parts.extend([form.city.data, form.state.data, form.zip_code.data])
            full_address = ', '.join(filter(None, address_parts))

            nta_result = app.geocoding_service.assign_nta(
                form.address_line_1.data,
                form.city.data,
                form.state.data,
                form.zip_code.data,
                app_id=app.config.get('NYC_GEOCLIENT_APP_ID'),
                app_key=app.config.get('NYC_GEOCLIENT_APP_KEY')
            )

            result = {
                'full_address': full_address,
                'nta_name': nta_result.get('nta_name', 'Unknown'),
                'nta_code': nta_result.get('nta_code', 'Unknown'),
                'source': nta_result.get('source', 'unknown')
            }

            log_manual_lookup(
                zip_code=form.zip_code.data,
                nta_found=(nta_result.get('nta_code', 'Unknown') != 'Unknown')
            )

            flash('Address lookup completed.', 'success')

        return render_template('manual_lookup.html', form=form, result=result)

    @app.route('/results')
    @login_required
    def show_results():
        results = get_user_results()
        result_count = len(results)
        processing_seconds = session.pop('last_processing_seconds', None)
        date_range = session.pop('last_date_range', 'all dates')
        timing_summary = session.pop('last_timing_details', None)

        if not results:
            flash('No results to display.', 'info')
            return redirect(url_for('select_source'))

        return render_template('results.html',
                               results=results,
                               result_count=result_count,
                               processing_seconds=processing_seconds,
                               date_range=date_range,
                               timing_summary=timing_summary)

    @app.route('/export-results')
    @login_required
    def export_results():
        results = get_user_results()

        if not results:
            flash('No results to export.', 'warning')
            return redirect(url_for('select_source'))

        log_data_export(survey_name='NTA Results', record_count=len(results))

        app.logger.info("\n" + "=" * 60)
        app.logger.info(f"EXPORT: {len(results)} results")
        if results:
            app.logger.info("First result:")
            for key, value in results[0].items():
                app.logger.info(f"  {key}: '{value}'")
        app.logger.info("=" * 60 + "\n")

        si = StringIO()
        fieldnames = [
            'record_id', 'date', 'first_name', 'last_name',
            'full_address', 'zip_code', 'nta_name', 'nta_code',
            'latitude', 'longitude', 'source', 'data_source'
        ]
        writer = csv.DictWriter(si, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()

        for result in results:
            writer.writerow({
                'record_id': result.get('record_id', ''),
                'date': result.get('date', ''),
                'first_name': result.get('first_name', ''),
                'last_name': result.get('last_name', ''),
                'full_address': result.get('full_address', ''),
                'zip_code': result.get('zip_code', ''),
                'nta_name': result.get('nta_name', ''),
                'nta_code': result.get('nta_code', ''),
                'latitude': result.get('latitude', ''),
                'longitude': result.get('longitude', ''),
                'source': result.get('source', ''),
                'data_source': result.get('data_source', '')
            })

        output = si.getvalue()
        si.close()

        return Response(
            output,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment;filename=nta_results.csv'}
        )

    # ==================== AUTH ROUTES ====================

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('index'))

        form = RegistrationForm()

        if form.validate_on_submit():
            existing = User.query.filter(
                (User.email == form.email.data) |
                (User.username == form.username.data)
            ).first()

            if existing:
                flash('Email or username already exists.', 'danger')
                return redirect(url_for('register'))

            user = User(username=form.username.data, email=form.email.data)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()

            flash('Account created! Please log in.', 'success')
            return redirect(url_for('login'))

        return render_template('register.html', form=form)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('index'))

        form = LoginForm()

        if form.validate_on_submit():
            user = User.query.filter_by(email=form.email.data).first()

            if user and user.check_password(form.password.data):
                login_user(user)
                user.last_login = datetime.utcnow()
                db.session.commit()
                log_login(username=user.username)  
                flash('Login successful.', 'success')
                return redirect(url_for('index'))

            flash('Invalid credentials.', 'danger')

        return render_template('login.html', form=form)

    @app.route('/logout')
    @login_required
    def logout():
        username = current_user.username
        clear_user_results()
        logout_user()
        log_logout(username=username)
        session.clear()
        flash('Logged out.', 'success')
        return redirect(url_for('login'))

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

    return app


app = create_app()

if __name__ == '__main__':
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    print("\n" + "=" * 60)
    print("  NTA Lookup Application Starting...")
    print("=" * 60)
    print(f"  Local URL: http://127.0.0.1:5002")
    print(f"  Network URL: http://{local_ip}:5002")
    print("  Share the Network URL with your team!")
    print("  Press CTRL+C to stop the server")
    print("=" * 60 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5002)