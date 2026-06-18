# NTA Lookup Application

The NTA Lookuup App is a Flask-based web application that converts full street addresses into their corresponding Neighborhood Tabulation Areas (NTAs) — geographic boundaries defined by the NYC Department of City Planning for demographic and statistical analysis.

## About This Version

# Production vs. Demonstration
This GitHub repository contains a demonstration version of the NTA Lookup Application adapted for public sharing on a personal account. It is not the production application deployed at NYU Langone Health.

Production Version (NYU Langone):

Integrates directly with REDCap for secure survey data retrieval 
Uses NYU Langone's internal geocoding service, which is HIPAA-compliant and designed to handle Protected Health Information (PII) securely 
Runs on NYU Langone's secure infrastructure with full audit logging and access controls 
Subject to institutional security policies and compliance requirements 

GitHub Demonstration Version (This Repository):

Uses LimeSurvey as a substitute for REDCap to demonstrate the survey data integration workflow 
Uses NYC Geocoding Service (a public service) for demonstration purposes only — not for production or sensitive data 
Intended for educational and portfolio purposes to showcase the application architecture and functionality
# Not suitable for handling real participant data or Protected Health Information

## Key Differences:

| Aspect            | NYU Langone Production                  | GitHub Demonstration                      |
|--------           |------------------------                 |----------------------                     |
| Survey Platform   | REDCap (secure, HIPAA-compliant) [2]    | LimeSurvey (for demo workflow only)       |
| Geocoding Service | NYU internal geocoding (PII-secure) [2] | NYC Geocoding Service (public, demo only) |
| Data Processing   | Local to NYU Langone network [2]        | Local to user environment                  
| Data Handling     | HIPAA-compliant with audit trails [2]   | No sensitive data; demo data only         |
| Deployment        | NYU Langone infrastructure [2]          | Personal/local development                |
| Use Case          | Community health program analysis [2]   | Portfolio demonstration and learning      |

## Important Disclaimer
Do not use this demonstration version with real participant data, Protected Health Information (PII), or any sensitive information. 

Step-by-Step Process
User Authentication — User logs in or registers via the Flask app
Data Source Selection — User chooses: Upload CSV, Connect to REDCap, or Manual Lookup
Address Input — Addresses are collected (file, API, or form)
Date Filter - Select Preset or Custom Date Filter
Geocoding — Each address is sent to the NYU Geoclient API, with a ZIP code–based fallback when the geocoding service is unavailable.
NTA Assignment — API returns NTA code and name for each address
Results Display — Matched results shown on the results page
Export — User downloads CSV with addresses and matched NTAs

## Problem Statement

Manual assignment of NTA codes to program participant addresses is time-consuming and labor-intensive:
- Manual processing time: ~2-3 minutes per record
- For 1,000 records: ~41 hours of manual work
- Human error risk: Inconsistent NTA assignments and data quality issues
- Data security concerns: Sharing participant data with third-party services risks HIPAA compliance violations

This application solves these challenges by automating NTA assignment with 99% time reduction while maintaining local data processing for enhanced security.

## Key Features

- Automated NTA Assignment: Instantly maps ZIP codes to NTAs with 99% time reduction
- Direct REDCap Integration: Fetches data via secure API without manual exports 
- Date Filtering: Filter records by date range to process only relevant subsets 
- Complete Records Only: Automatically filters for completed survey responses to ensure clean data 
- Local Geocoding: ZIP-to-NTA mapping processed entirely on local servers with no external data transmission 
- One-Click Export: Download results as CSV for further analysis 
- User Authentication: Secure login system with role-based access control and audit trail 
- HIPAA Compliance: Local processing eliminates third-party risks and maintains data security 

## Benefits

Time Savings 

Manual process: ~2-3 minutes per record
Automated process: ~1 second per record
For 1,000 records: ~41 hours saved (~$1,458 at $35/hour labor cost)

Data Security 

Local processing only—no third-party data sharing
Data stays within organization network
Reduces data breach risks

Accuracy 

Eliminates human error in manual lookups
Consistent NTA assignments
Standardized output format

Safeguards

The application includes the following safeguards:

Administrative Safeguards

User authentication required
Role-based access (registered users only)
Audit trail via server logs

Technical Safeguards

Data encrypted in transit (HTTPS)
Session time-out after inactivity
No persistent storage of processed results
Local processing eliminates third-party risks

Physical Safeguards

Application runs on organization's infrastructure
Data center security controls apply
Access logs stored on secure servers

# Troubleshooting

| Issue                | Cause                                         | Solution                                           |
|-------               |-------                                        |----------                                          |
| "No records found"   | Date range too narrow or no completed records | Expand date range or check survey sources for data |
| "API not configured" | Missing API token in .env file                | Add correct token to .env file                     |
| "Connection refused" | Server crashed                                | Check terminal for error, restart Flask            |
| "Unknown NTA"        | ZIP code not in mapping file                  | Verify ZIP code is valid NYC ZIP                   |
| Slow performance      Too many records                               | Use date filter to reduce batch size               |

## Architecture

For detailed system design, components, and data flow, see [ARCHITECTURE.md](docs/ARCHITECTURE.md)

The application follows a layered architecture:

Frontend Layer: HTML5 + Bootstrap 5 for user interface
Backend Layer: Python Flask for business logic and API handling
Data Layer: SQLite for user authentication; local ZIP-to-NTA mapping
Integration Layer: survey API for secure data retrieval; NYC Geoclient APIs

## Contributing
Please follow these guidelines when contributing:

Create feature branches for new work
Write clear commit messages
Test changes before submitting pull requests
Update documentation as needed
Do not commit sensitive credentials or API keys


## Technologies Used

- Backend: Python 3.14, Flask 
- Frontend: HTML5, Bootstrap 5, JavaScript
- Database: SQLite 
- APIs:  LimeSurvey API, NYC Geoclient APIs 
- Authentication: User authentication system with audit logging 

## Installation Instructions

⚠️ **Warning:** This is a demonstration version using public APIs and LimeSurvey.
- Use test data only.
- Do not process real participant information.
- Do not use NYC Geocoding Service with sensitive data.


## Prerequisites

- Python 3.8+
- REDCap instance with API access (optional)
- LimeSurvey instance with API access
- NYC Geoclient API credentials


### Setup Steps

```bash
# 1. Clone or download the application
git clone https://github.com/irchorn/nta-lookup-app.git
cd nta-lookup-app

# 2. Create virtual environment
python -m venv venv

# 3. Activate virtual environment
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure environment variables
# Edit .env file with your API tokens
# Required: LimeSurvey API token , REDCap API token (if used), NYC Geoclient API credentials

# 6. Run the application
python app.py
```

## Support
For issues, questions, or feature requests:

Open an issue on GitHub
Contact: [irchorn@gmail.com]
Documentation: See /docs folder

## Developer
Iryna Chornopys
irchorn@gmail.com

## License
MIT License (see LICENSE.md)
References: Application documentation and user guide for technical details, benefits, features, installation, and security/compliance notes.