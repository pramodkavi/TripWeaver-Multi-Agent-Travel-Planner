# User Guide

TripWeaver is a chat assistant that helps you plan travel — ask general
questions, search hotels and flights, and book them, all in plain language.

## Getting started
Open the app (locally at <http://localhost:7860>, or your deployed Space URL)
and type into the chat box. You never choose an agent — TripWeaver works out
what you want and routes it automatically.

## What you can ask

### General travel questions
> "What's the best time to visit Japan?"
> "Do I need a visa for Thailand?"

The assistant answers conversationally. It won't invent specific hotel/flight
details — it offers to search for those instead.

### Hotels
> "Find hotels in Bangkok"
> "Show me all hotels"
> "Hotels in Singapore from 2026-06-01 to 2026-06-05"

Results appear as a table with name, city, star rating, price/night, rooms, and
an **ID** you use to book.

### Flights
> "Flights from NRT to ICN"
> "Flights from CMB to BKK on 2025-11-15"
> "Show all flights"

> **Note:** use **airport codes** (e.g. `NRT`, `ICN`), not city names. A
> city-name search will honestly report no results.

### Booking
Use an ID from a search result and provide the required details:
> "Book hotel <hotel-id> for John Doe, john@example.com, double, 2026-06-01 to 2026-06-05"
> "Book flight <flight-id> for Jane Smith, jane@example.com"

If anything required is missing, TripWeaver asks a follow-up question rather
than guessing.

## What the status cues mean
While working, the assistant shows what it is doing:
- **Understanding your request…** — routing to the right agent
- **Searching…/Booking…** — calling a live travel service
- then the answer streams in word by word.

## If something goes wrong
If a travel service is temporarily unavailable, you'll see a short, friendly
message (never a technical error), and the rest of the assistant keeps working.
Try again shortly, or ask something else.

## Tips
- Use the example buttons under the chat to try common queries.
- Refer back to a previous result by its ID when booking.
- Press **Clear** to start a fresh conversation.

_(Screenshots can be added here.)_
