from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, PasswordField, SubmitField, SelectField, TextAreaField, DateField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional
from wtforms import RadioField, SubmitField

class RegistrationForm(FlaskForm):
    """Registration form for new users."""
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=3, max=80, message="Username must be between 3 and 80 characters.")
    ])
    email = StringField('Email', validators=[
        DataRequired(),
        Email(message="Please enter a valid email address.")
    ])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, message="Password must be at least 8 characters.")
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message="Passwords must match.")
    ])
    submit = SubmitField('Register')


class LoginForm(FlaskForm):
    """Login form for existing users."""
    email = StringField('Email', validators=[
        DataRequired(),
        Email(message="Please enter a valid email address.")
    ])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


class CSVUploadForm(FlaskForm):
    """Form for uploading REDCap CSV export."""
    csv_file = FileField('REDCap CSV Export', validators=[
        FileRequired(message="Please select a CSV file."),
        FileAllowed(['csv'], message="Only CSV files are allowed.")
    ])
    submit = SubmitField('Upload and Process')


class AddressLookupForm(FlaskForm):
    """Form for manual address lookup."""
    address_line_1 = StringField('Address Line 1', validators=[DataRequired()])
    address_line_2 = StringField('Address Line 2', validators=[Optional()])
    city = StringField('City', validators=[DataRequired()])
    state = StringField('State', validators=[DataRequired()])
    zip_code = StringField('ZIP Code', validators=[DataRequired(), Length(min=5, max=10)])
    submit = SubmitField('Look Up NTA')


class DataSourceForm(FlaskForm):
    
    date_filter_type = SelectField(
        'Date Filter Type',
        choices=[
            ('all', 'All Dates'),
            ('preset', 'Preset Range'),
            ('custom', 'Custom Range')
        ],
        default='all'
    )

    preset_range = SelectField(
        'Preset Range',
        choices=[
            ('7days', 'Last 7 Days'),
            ('30days', 'Last 30 Days'),
            ('90days', 'Last 90 Days'),
            ('thismonth', 'This Month'),
            ('lastmonth', 'Last Month'),
            ('thisyear', 'This Year'),
            ('lastyear', 'Last Year')
        ],
        validators=[Optional()]
    )

    start_date = DateField('Start Date', validators=[Optional()])
    end_date = DateField('End Date', validators=[Optional()])


    data_source = RadioField(
        'Select Data Source',
        choices=[
            ('api', 'REDCap API'),
            ('limesurvey', 'LimeSurvey API'),
            ('csv', 'Upload CSV')
        ],
        default='csv'
    )
    submit = SubmitField('Continue')