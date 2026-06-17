import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from flask import request
from flask_login import current_user
import os


def setup_audit_logger(app):
    """Configure audit logging for the application."""
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(app.config.get('BASE_DIR', '.'), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Create audit logger
    audit_logger = logging.getLogger('audit')
    audit_logger.setLevel(logging.INFO)
    
    # Rotating file handler - keeps last 10 files of 10MB each
    handler = RotatingFileHandler(
        os.path.join(log_dir, 'audit.log'),
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=10
    )
    
    # Log format
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    audit_logger.addHandler(handler)
    
    return audit_logger


def log_audit_event(event_type, details=None, success=True):
    """
    Log an audit event.
    
    Args:
        event_type: Type of event (LOGIN, LOGOUT, FETCH_DATA, EXPORT, etc.)
        details: Dictionary of additional details
        success: Whether the action was successful
    """
    audit_logger = logging.getLogger('audit')
    
    # Get user info
    if current_user and current_user.is_authenticated:
        user_info = f"user={current_user.username} (id={current_user.id})"
    else:
        user_info = "user=anonymous"
    
    # Get request info
    try:
        ip_address = request.remote_addr
        user_agent = request.user_agent.string[:100] if request.user_agent else 'unknown'
    except RuntimeError:
        ip_address = 'unknown'
        user_agent = 'unknown'
    
    # Build log message
    status = "SUCCESS" if success else "FAILED"
    
    message_parts = [
        f"EVENT={event_type}",
        f"STATUS={status}",
        user_info,
        f"ip={ip_address}"
    ]
    
    if details:
        for key, value in details.items():
            message_parts.append(f"{key}={value}")
    
    message = " | ".join(message_parts)
    
    if success:
        audit_logger.info(message)
    else:
        audit_logger.warning(message)


# Convenience functions for common events
def log_login(username, success=True):
    log_audit_event('LOGIN', {'username': username}, success)


def log_logout(username):
    log_audit_event('LOGOUT', {'username': username}, True)


def log_data_fetch(survey_key, survey_name, record_count, date_range=None, success=True):
    details = {
        'survey_key': survey_key,
        'survey_name': survey_name,
        'record_count': record_count
    }
    if date_range:
        details['date_range'] = date_range
    log_audit_event('FETCH_DATA', details, success)


def log_data_export(survey_name, record_count, success=True):
    log_audit_event('EXPORT_DATA', {
        'survey_name': survey_name,
        'record_count': record_count
    }, success)


def log_csv_upload(filename, record_count, success=True):
    log_audit_event('CSV_UPLOAD', {
        'filename': filename,
        'record_count': record_count
    }, success)


def log_manual_lookup(zip_code, nta_found, success=True):
    log_audit_event('MANUAL_LOOKUP', {
        'zip_code': zip_code,
        'nta_found': nta_found
    }, success)


def log_access_denied(resource, reason=None):
    details = {'resource': resource}
    if reason:
        details['reason'] = reason
    log_audit_event('ACCESS_DENIED', details, False)