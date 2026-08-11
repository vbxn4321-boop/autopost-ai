# AutoPost AI - Project Handoff & Context Document

## 1. Project Overview
- **Project Name:** AutoPost AI
- **Goal:** A fully automated social media posting web application that generates videos using Gemini API and posts them simultaneously to multiple platforms (Instagram, TikTok, Naver Blog, X/Twitter, Facebook, Threads).
- **Tech Stack:** Python (Flask), SQLite, HTML/Vanilla CSS/Vanilla JS.
- **Hosting:** Render (Web Service) `https://autopost-ai-bcwk.onrender.com`.

## 2. Chronological Development History
1. **Initial Setup & Architecture:**
   - Set up the Flask backend and SQLite database (`posts.db`).
   - Created a highly modular structure (`app.py`, `config.py`, `core/` directory for integrations).
2. **Video Generation & AI Engine:**
   - Integrated Google Gemini API (gemini-flash-latest) for generating viral scripts, captions, and hashtags.
   - Implemented a robust video generation pipeline (FFmpeg/MoviePy) to handle text overlays, background videos, and BGM merging.
3. **Platform Integrations (Core):**
   - **Instagram:** Meta Graph API integration for Reels publishing.
   - **Naver Blog:** OAuth 2.0 implementation and posting API.
   - **X (Twitter) & Others:** API structures prepared.
4. **UI/UX Development:**
   - Created a modern, sleek, premium dashboard (`index.html`, `style.css`) with neon accents and dark mode aesthetics.
   - Implemented real-time progress bars, video preview modals, and dynamic platform selection toggles using Vanilla JS.
5. **Deployment Journey:**
   - **Vercel:** Attempted deployment, but failed due to the 250MB serverless function limit (heavy dependencies like PyTorch/FFmpeg/MoviePy caused the build to fail).
   - **Render:** Successfully migrated and deployed to Render as a Web Service. Configured environment variables and handled background task processing.
6. **Current Status & Roadblocks (TikTok):**
   - Implemented TikTok OAuth2 (PKCE) and Content Posting API logic in `core/oauth_tiktok.py`.
   - **Current Blocker:** The TikTok Developer Portal configuration is extremely buggy. We are stuck in an infinite loop with the Sandbox Redirect URI validation (TikTok's UI is rejecting `https://`, `localhost`, and `127.0.0.1` due to contradictory internal validation rules between Web and Desktop app types).
   - Development on TikTok is temporarily paused by the user to prevent burnout.

## 3. Codebase Structure
- `app.py`: Main Flask application, routing, API endpoints, and background task handling.
- `config.py`: Global configurations, environment variables, and platform-specific limits (aspect ratios, char limits).
- `core/`: 
  - `oauth_tiktok.py`, `oauth_naver.py`: Authentication flows.
  - `instagram.py`, `naver_blog.py`: Platform-specific posting logic.
  - `video_maker.py`: Core video generation and rendering logic.
  - `gemini_api.py`: AI text and script generation.
- `templates/`, `static/`: Frontend assets (HTML, CSS, JS).
- `data/`: SQLite database storage location.

## 4. Current Environment Variables (Required in Render)
- `GEMINI_API_KEY`
- `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET` (Currently set to Sandbox keys)
- `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`
- Redirect URIs are hardcoded to the Render URL in `config.py` for stability.

## 5. Next Steps for Claude Code
- Claude Code should read the existing codebase to understand the exact syntax and patterns used.
- Do not attempt to fix the TikTok Developer Portal UI issues, as they are on TikTok's server side.
- Focus on extending other functionalities (e.g., adding user accounts, improving video rendering speed, or integrating the remaining platforms).
