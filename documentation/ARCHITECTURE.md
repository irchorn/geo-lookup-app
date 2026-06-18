# NTA Lookup App - Architecture Documentation

## Overview

The NTA Lookup Application is a web-based tool that automatically assigns Neighborhood Tabulation Areas (NTAs) to participant addresses from REDCap surveys. This document describes the system architecture, components, data flow, and design decisions.

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | HTML5, Bootstrap 5, JavaScript | User interface and client-side interactions |
| **Backend** | Python 3.11, Flask | Web server and business logic |
| **Database** | SQLite | User authentication and session storage |
| **APIs** | REDCap API, NYU Geocoding APIs | Data retrieval and geocoding services |
| **Deployment** | NYU Langone Infrastructure | Secure, HIPAA-compliant hosting |

## System Components

### 1. Frontend Layer
- **HTML5/Bootstrap 5:** Responsive user interface
- **JavaScript:** Client-side form validation and UX interactions
- **Purpose:** Provides intuitive interface for users to fetch data, configure options, and export results

### 2. Backend Layer (Flask)
- **Authentication Module:** User login, registration, session management
- **REDCap Integration Module:** Secure API calls to fetch survey data
- **Geocoding Module:** ZIP code to NTA mapping and validation
- **Export Module:** CSV generation and download functionality
- **Audit Logging Module:** Tracks all user actions for HIPAA compliance

### 3. Data Layer (SQLite)
- **Users Table:** Stores user credentials and profiles
- **Sessions Table:** Manages active user sessions
- **Audit Log Table:** Records all data access and actions
- **NTA Mapping Table:** ZIP code to NTA boundary mappings (cached locally)

### 4. External APIs
- **REDCap API:** Retrieves survey responses securely via encrypted transmission
- **NYU Geocoding APIs:** Maps addresses/ZIP codes to NTA codes

## Data Flow Architecture

### Standard Processing Flow

User Input
↓
User Authentication
↓
REDCap Data Fetch (via secure API)
↓
Data Validation & Filtering
↓
ZIP-to-NTA Geocoding (Local Processing)
↓
Results Display
↓
CSV Export
↓
Audit Log Entry



### Detailed Steps

1. **User Authentication**
   - User enters credentials
   - System validates against SQLite user database
   - Session token generated with timeout

2. **Data Retrieval**
   - User specifies date range and filters
   - Flask backend calls REDCap API with encrypted authentication token
   - REDCap returns JSON response with survey records

3. **Data Processing**
   - Filter for completed records only (data quality)
   - Extract address and ZIP code fields
   - Validate data format

4. **Geocoding (Local)**
   - ZIP codes matched against local NTA mapping database
   - No external third-party processing
   - Instant results without network latency

5. **Results Compilation**
   - Generate results with NTA code, name, and borough
   - Display in table format on frontend
   - Store temporarily in memory (no persistent storage)

6. **Export & Cleanup**
   - User downloads CSV file
   - Results cleared from memory
   - Action logged to audit trail

## Key Design Decisions

### 1. Local Geocoding (vs. Third-Party Services)

**Decision:** Process all ZIP-to-NTA mapping locally on NYU Langone servers

**Rationale:**
- ✅ **Data Security:** Participant data never leaves NYU Langone network [2]
- ✅ **HIPAA Conscious:** No Business Associate Agreement required with external vendors [2]
- ✅ **Performance:** ~1 second per record vs. external API delays [2]
- ✅ **Cost:** No per-transaction fees; batch processing unlimited
- ✅ **Compliance:** Meets institutional security policies [2]

**Trade-off:** Requires maintaining local NTA mapping data

---

### 2. SQLite Database (vs. PostgreSQL/MongoDB)

**Decision:** Use SQLite for user authentication and audit logging

**Rationale:**
- ✅ **Simplicity:** Single-file database, no external server required
- ✅ **Security:** Database file stored on secure NYU infrastructure [2]
- ✅ **Low Overhead:** Minimal resource requirements for small user base
- ✅ **HIPAA-Compatible:** When used on secure infrastructure [2]

**Scalability Note:** For >500 concurrent users, consider migration to PostgreSQL

---

### 3. Direct REDCap Integration (vs. Manual Export)

**Decision:** Use REDCap API for direct data retrieval instead of manual file uploads

**Rationale:**
- ✅ **Automation:** Eliminates manual export/import steps
- ✅ **Real-time:** Always processes current data
- ✅ **Security:** Encrypted API transmission [2]
- ✅ **Audit Trail:** REDCap API logs all access attempts [2]

**Requirements:** Valid REDCap API token stored in `.env` file (never committed to repo)

---

### 4. No Persistent Data Storage

**Decision:** Do not save processed results to disk; clear from memory after export

**Rationale:**
- ✅ **Privacy:** Minimizes sensitive data retention
- ✅ **HIPAA Compliance:** Session time-outs and no persistent storage [2]
- ✅ **Compliance:** Meets minimum necessary standard
- ✅ **Auditability:** Reduces potential breach surface

**Implication:** Users must export results immediately; re-processing required for future access

---

## Security Architecture

### Administrative Safeguards [2]
- User authentication required for all features
- Role-based access control (registered users only)
- Comprehensive audit trail via server logs
- Session timeout after inactivity

### Technical Safeguards [2]
- Data encrypted in transit (HTTPS only)
- Session time-out after inactivity
- No persistent storage of processed results
- Local processing eliminates third-party risks
- Input validation and sanitization

### Physical Safeguards [2]
- Application runs on NYU Langone infrastructure
- Data center security controls apply
- Access logs stored on secure servers
- Network firewalls and intrusion detection

### Audit Logging [2]

All user actions are logged with:
- **User identity:** Who accessed data (§164.312(b))
- **Timestamp:** When data was accessed (§164.312(b))
- **Performed action:** What action was done (§164.312(b))
- **Data accessed:** Which records/surveys were accessed (§164.312(b))
- **API address:** Access location (§164.312(b))
- **Success/Failure:** Unauthorized attempt tracking (§164.312(b))

---

## HIPAA Compliance Architecture

### Encryption & Transport
- HTTPS for all data in transit
- TLS 1.2+ minimum
- No unencrypted data transmission

### Access Control
- Multi-factor authentication (recommended)
- Role-based access policies
- Session management with automatic logout

### Data Minimization
- Only necessary fields extracted from REDCap
- No retention of processed results
- Temporary memory storage only

### Audit & Accountability
- Complete audit trail of all access
- Immutable log records
- Regular audit log reviews


## Application Flow Diagrams

### User Session Flow
Start
↓
Navigate to App
↓
Already logged in? → Yes → Go to Dashboard
↓ No
Register/Login
↓
Credentials valid? → No → Show error, retry
↓ Yes
Create session with timeout
↓
Dashboard
↓
User chooses action:
├→ Fetch from REDCap/LimeSurvey
├→ Configure filters
├→ Process records
├→ View results
└→ Export CSV
↓
Logout or Session timeout
↓
End

### Data Processing Pipeline
Survey Database
↓
[API Call]
↓
Flask Backend
├─ Validate authentication
├─ Filter by date range
├─ Filter for completed records
└─ Extract address/ZIP fields
↓
Local Geocoding Engine
├─ Match ZIP codes
├─ Lookup NTA codes
└─ Validate results
↓
Results Formatter
├─ Compile output
├─ Format for display
└─ Prepare for export
↓
Frontend Display
├─ Show results table
├─ Display summary stats
└─ Enable CSV download
↓
Audit Logger
├─ Record user action
├─ Timestamp access
└─ Log any errors
---

## Performance Characteristics

### Processing Speed [2]

| Operation | Time |
|-----------|------|
| Single record NTA lookup | ~1 second |
| 100 records batch | ~1-2 minutes |
| 1,000 records batch | ~10-15 minutes |
| Manual equivalent (1,000 records) | ~41 hours |
| **Time reduction** | **99%** |

### Recommended Batch Sizes

- **Optimal:** 100-500 records per job
- **Acceptable:** Up to 2,000 records
- **Max:** 5,000 records (with date filtering)

If processing >1,000 records, use date filtering to split into smaller batches.

---

## Scalability Considerations

### Current Capacity
- **Concurrent users:** Up to 50
- **Records per job:** Up to 5,000
- **Storage:** Minimal (~100 MB for NTA mapping data)

### Future Scaling Options
1. **Database:** Migrate SQLite → PostgreSQL for multi-server support
2. **Caching:** Add Redis for session management and results caching
3. **Async Processing:** Use Celery for background job processing of large batches
4. **Load Balancing:** Add reverse proxy (nginx) for multiple Flask instances

---

## Dependencies

### Python Packages
- **Flask:** Web framework
- **geopandas:** Geospatial data processing
- **shapely:** Geometric operations
- **requests:** HTTP library for API calls
- **python-dotenv:** Environment variable management
- **werkzeug:** Password hashing and security utilities

See `requirements.txt` for complete list and versions.

---

## Error Handling Strategy

### Common Errors & Recovery

| Error | Cause | Recovery |
|-------|-------|----------|
| "No records found" | Date range too narrow | Expand date range [2] |
| "API not configured" | Missing .env token | Add REDCap API token [2] |
| "Connection refused" | Server crashed | Restart Flask app [2] |
| "Unknown NTA" | Invalid ZIP code | Validate ZIP code format [2] |
| Slow performance | Too many records | Use date filter [2] |

---

## Future Enhancements

### Planned Features
- [ ] Batch job scheduling (process large exports overnight)
- [ ] Advanced mapping visualization (interactive map display)
- [ ] Multi-field geocoding (address + ZIP code verification)
- [ ] API endpoint for programmatic access
- [ ] Data caching and offline mode support
- [ ] Advanced analytics dashboard

### Under Consideration
- [ ] Mobile app (iOS/Android)
- [ ] Real-time data sync with REDCap
- [ ] Machine learning for address validation
- [ ] Multi-language support

---

## Support & Questions

For architecture questions or design discussions:
- Review relevant code in `app/` directory
- Check data flow diagrams above
- See QUICKSTART.md for setup issues
- Contact: irchorn@gmail.com

---

**Version:** 1.0  
**Last Updated:** May 2026  
**Maintained by:** Iryna Chornopys