# Art CRM - TODO & Future Enhancements

## Phase 6-Alpha: Lead Generation (IN PROGRESS)
- [x] Set up TODO file
- [ ] Add Google Maps API integration
- [ ] Add OpenStreetMap fallback
- [ ] Add web scraping fallback
- [ ] Implement lead scoring with Ollama
- [ ] Add `crm recon` CLI command
- [ ] Test with real cities (Rosenheim, Augsburg)

## Future Enhancements (Noted During Development)

### Lead Generation
- [ ] **Google Maps API** - Enhance integration with more filters (rating, hours, reviews)
- [ ] **Contact validation** - Check if emails/websites are reachable before storing
- [ ] **Bulk city search** - Search multiple cities at once (e.g., all of Bavaria)
- [ ] **Regional search** - Search by region/state instead of just city (e.g., "Bavaria")
- [ ] **Additional business types** - Add hotels, offices, bookstores, museums, etc.
- [ ] **Photo scraping** - Download venue photos to assess aesthetic fit
- [ ] **Social media integration** - Find Instagram/Facebook pages for venues

### Email Integration (Phase 7)
- [ ] **SMTP/IMAP setup** - Send emails directly from CLI
- [ ] **Email tracking** - Track opens, clicks, replies
- [ ] **Auto-reply detection** - Detect out-of-office or bounce messages
- [ ] **Bulk send** - Send to multiple contacts at once with rate limiting
- [ ] **Email templates** - Save and reuse common templates

### Data Quality
- [ ] **Duplicate detection** - More sophisticated fuzzy matching for duplicates
- [ ] **Data enrichment** - Auto-fill missing fields from web searches
- [ ] **Venue categorization** - Better AI categorization of venue subtypes
- [ ] **Contact verification** - Verify phone numbers, email formats

### AI Features
- [ ] **Sentiment analysis** - Analyze interaction history for relationship health
- [ ] **Success prediction** - Predict likelihood of success based on historical data
- [ ] **Optimal timing** - AI suggests best day/time to contact based on patterns
- [ ] **Personalization engine** - Auto-generate personalized opening lines

### Reporting & Analytics
- [ ] **Dashboard** - Weekly/monthly stats (contacts added, shows booked, etc.)
- [ ] **Success metrics** - Track conversion rates by venue type, city, approach
- [ ] **Export reports** - PDF/Excel reports for record-keeping

### Web & GUI (Phases 8-10)
- [ ] **FastAPI backend** - REST API for all CRM operations
- [ ] **Browser UI** - Modern web interface (React/Vue?)
- [ ] **Tkinter desktop app** - Native desktop GUI for offline use
- [ ] **Mobile app** - iOS/Android app (future consideration)

### Infrastructure
- [ ] **VPS deployment** - Deploy to production server
- [ ] **Automated backups** - Daily database backups to cloud storage
- [ ] **Monitoring** - Error tracking, performance monitoring
- [ ] **Multi-user support** - Multiple artists sharing one CRM instance

## Known Issues / Incomplete Work
- [x] **Spreadsheet import** — CONFIRMED COMPLETE. All 144 real contacts imported (593 rows
      in sheet includes blank rows, section headers, URLs — not real contacts). 207 total
      contacts in DB is correct.
- [ ] **Many contacts are cold/uncontacted** — ~96 contacts have no type set, many have
      status='cold' with zero interactions. Use `crm suggest` and `crm recon` to work through them.

## Ideas / Nice to Have
- Voice notes for interactions (record audio, auto-transcribe)
- Integration with calendar (Google Calendar, iCal)
- Exhibition management (track artwork, pricing, sales)
- Invoice generation for sales
- Gallery relationship scoring (track responsiveness, professionalism)

---

**Last updated:** 2026-02-12
