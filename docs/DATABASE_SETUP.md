# PostgreSQL Setup for Art CRM

## Installation

### Ubuntu/Debian
```bash
# Update package list
sudo apt update

# Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# Start and enable PostgreSQL service
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Verify installation
psql --version
```

### Check PostgreSQL is running
```bash
sudo systemctl status postgresql
```

## Database Configuration

### 1. Create Database User and Database

```bash
# Switch to postgres user
sudo -u postgres psql

# In the PostgreSQL prompt, run:
CREATE USER artcrm_admindude WITH PASSWORD 'aw4e0rfeA1!Q';
CREATE DATABASE artcrm OWNER artcrm_admindude;
GRANT ALL PRIVILEGES ON DATABASE artcrm TO artcrm_admindude;

# Exit PostgreSQL prompt
\q
```

### 2. Test Connection

```bash
# Test connecting to the database
psql -U artcrm_admindude -d artcrm -h localhost

# You should see the PostgreSQL prompt. Exit with:
\q
```

If the connection fails with "peer authentication failed", you may need to configure PostgreSQL to use password authentication:

```bash
# Edit pg_hba.conf (location may vary)
sudo nano /etc/postgresql/*/main/pg_hba.conf

# Find the line that looks like:
# local   all             all                                     peer

# Change it to:
# local   all             all                                     md5

# Restart PostgreSQL
sudo systemctl restart postgresql
```

### 3. Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# The DATABASE_URL is already configured with the correct credentials
# Edit .env if you need to change any settings
```

### 4. Install Python Dependencies

```bash
# Create virtual environment
python3.12 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies (will be created in next phases)
pip install psycopg2-binary python-dotenv
```

## Running Migrations

Migrations are SQL files in `artcrm/db/migrations/` directory. They must be run in order.

### Manual Migration (Phase 1)

```bash
# Run each migration file in order
psql -U artcrm_admindude -d artcrm -h localhost -f artcrm/db/migrations/001_initial_schema.sql
psql -U artcrm_admindude -d artcrm -h localhost -f artcrm/db/migrations/002_seed_lookup_values.sql
```

### Verify Setup

```bash
# Connect to database
psql -U artcrm_admindude -d artcrm -h localhost

# List all tables
\dt

# You should see:
# - schema_migrations
# - lookup_values
# - contacts
# - interactions
# - shows
# - ai_analysis
# - people

# Check lookup_values has data
SELECT category, COUNT(*) FROM lookup_values GROUP BY category;

# Exit
\q
```

## Troubleshooting

### "psql: command not found"
PostgreSQL client tools are not in your PATH. Install them:
```bash
sudo apt install postgresql-client
```

### "peer authentication failed"
See the pg_hba.conf configuration above.

### "database does not exist"
Re-run the CREATE DATABASE command from step 1.

### Connection refused
PostgreSQL service is not running:
```bash
sudo systemctl start postgresql
```

## VPS Deployment Notes

For VPS deployment, the same steps apply, but:
- Ensure PostgreSQL allows connections from your application's network interface
- Use strong passwords (different from the example above)
- Configure firewall rules to restrict database access
- Consider using Unix socket connections instead of TCP for better security
- Set up regular backups using `pg_dump`

Example backup command:
```bash
pg_dump -U artcrm_admindude -d artcrm -h localhost > backup_$(date +%Y%m%d_%H%M%S).sql
```

Example restore command:
```bash
psql -U artcrm_admindude -d artcrm -h localhost < backup_20260212_120000.sql
```
