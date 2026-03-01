# Google Maps API Setup Guide

## Getting Your API Key

The lead scout feature uses Google Maps Places API to find galleries, cafes, and co-working spaces. You need an API key to use this feature.

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Sign in with your Google account
3. Click "Select a project" → "New Project"
4. Name it "Art CRM" (or whatever you like)
5. Click "Create"

### Step 2: Enable Places API

1. In your new project, go to "APIs & Services" → "Library"
2. Search for "Places API"
3. Click "Places API"
4. Click "Enable"

### Step 3: Create API Key

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "API Key"
3. Copy your API key (looks like: `AIzaSyD...`)
4. Click "Restrict Key" (recommended for security)

### Step 4: Restrict API Key (Optional but Recommended)

1. Under "Application restrictions":
   - Select "IP addresses"
   - Add your server's IP or `0.0.0.0/0` for any IP (less secure)

2. Under "API restrictions":
   - Select "Restrict key"
   - Check "Places API"
   - Click "Save"

### Step 5: Add to .env File

1. Open your `.env` file in the project root
2. Add the line:
   ```
   GOOGLE_MAPS_API_KEY=AIzaSyD...your-actual-key-here
   ```
3. Save the file

### Pricing & Free Tier

- **Free tier**: $200/month credit (roughly 28,000 Places API requests)
- **After free tier**: ~$17 per 1,000 requests
- For reference: Scouting one city with 3 business types = ~30-100 requests

**Free tier is enough for** scouting ~100-200 cities per month.

### Testing Your Setup

Run this command to test:
```bash
./crm recon Rosenheim DE --type gallery
```

If it works, you'll see venues being discovered! If you see "GOOGLE_MAPS_API_KEY not set", check your .env file.

### Troubleshooting

**"API key not valid"**
- Make sure you copied the full key from Google Cloud Console
- Check there are no extra spaces in your .env file
- Make sure Places API is enabled for your project

**"This API project is not authorized"**
- Go to Google Cloud Console → APIs & Services → Library
- Make sure "Places API" is enabled (not just "Maps JavaScript API")

**"You have exceeded your rate limit"**
- You've hit the free tier limit
- Wait until next month, or add billing to your Google Cloud account

**"Request denied"**
- Check your API key restrictions
- Make sure your IP is allowed if you set IP restrictions

## Alternative: OpenStreetMap Only

If you don't want to set up Google Maps API, you can use OpenStreetMap only:

```bash
./crm recon Rosenheim DE --no-google
```

This uses free OpenStreetMap data, but coverage may be incomplete compared to Google Maps.

---

**Need help?** Check the [Google Maps Platform documentation](https://developers.google.com/maps/documentation/places/web-service/overview)
