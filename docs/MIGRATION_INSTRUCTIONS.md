# Postgres Account Migration Instructions

## Step 1: Get your DATABASE_URL

### From Streamlit Cloud:
1. Go to https://share.streamlit.io/
2. Click on your app (saddl)
3. Click Settings (⚙️) → Secrets
4. Copy the `DATABASE_URL` value

It should look like:
```
postgresql://postgres.xxx:password@aws-0-us-west-1.pooler.supabase.com:6543/postgres
```

## Step 2: Create .env file

In the `/saddle` root directory (NOT `/saddle/desktop`), create a `.env` file:

```bash
cd /path/to/saddle
echo "DATABASE_URL=your_database_url_here" > .env
```

Replace `your_database_url_here` with your actual DATABASE_URL from Step 1.

## Step 3: Run the migration

```bash
cd /path/to/saddle/desktop

# Test first with dry-run
python3 migrate_orphaned_accounts_postgres.py --dry-run

# If dry-run looks good, run for real
python3 migrate_orphaned_accounts_postgres.py
```

## What it does:

1. Connects to your Postgres database
2. Finds all accounts without `organization_id`
3. Assigns them to the Primary Organization
4. Your accounts will appear in Settings > Ad Accounts

## Troubleshooting:

**"DATABASE_URL not found"**
- Make sure .env file is in `/saddle/.env` (root folder)
- Check the file contains: `DATABASE_URL=postgresql://...`

**"psycopg2 not installed"**
- Install with: `pip install psycopg2-binary`

**"No account table found"**
- Your database schema hasn't been initialized yet
- Run the app first to create tables
