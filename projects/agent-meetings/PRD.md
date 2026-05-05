# Product Requirements Document (PRD): Project React

## 1. Project Overview
**Name:** Project React
**Platform:** iOS (Apple App Store), Android (Google Play Store), and Web (Browser)
**Objective:** A real-time video/audio conferencing application where humans and AI agents interact seamlessly in a shared meeting environment (similar to Zoom or MS Teams).
**Core Differentiator:** AI agents are first-class participants capable of listening, processing, and responding in real-time with highly natural, conversational voices.

## 2. Key Features (MVP)
1. **Cross-Platform Support:** Users can join meetings natively from iOS, Android devices, or directly through a Web browser.
2. **Real-time Conferencing:** Low-latency video and audio streaming for human participants.
3. **Universal Link Joining:** Anyone with a meeting link can join the room seamlessly (deep linking for mobile apps, direct URL routing for web).
4. **AI Agent Participants (Internal & External):** 
   - **Internal Agents:** Platform-hosted agents that use advanced Speech-to-Speech models (e.g., OpenAI Realtime API) for human-like inflection and interruption handling.
   - **External Third-Party Agents:** Outside AI agents can join via the meeting link. This will be supported by providing a headless API / WebSocket connection, or via SIP dial-in so external frameworks can pipe their audio into our rooms.
5. **Room Management:** Create rooms, generate shareable links, and manage participants.

## 3. Technology Stack
*   **Frontend (Mobile & Web):** React Native with Expo (allows compiling to iOS, Android, and React Native Web from a single codebase) or a companion Next.js web app.
*   **WebRTC / Real-Time Infrastructure:** LiveKit (LiveKit Cloud or Self-hosted)
*   **AI Orchestration:** LiveKit Agents Framework (Python/Node.js)
*   **External Agent Gateway:** LiveKit SIP Integration or Open API webhook for third-party bots.
*   **AI Pipeline for "Natural Voice":** OpenAI Realtime API (lowest latency, highly conversational, handles interruptions natively).

## 4. Phased Development Plan

### Phase 1: Proof of Concept (The "Hello World" of AI Meetings)
*   **Goal:** Validate the real-time AI audio loop and link joining.
*   **Tasks:**
    *   Set up a LiveKit Cloud project.
    *   Create a basic React/Expo app (web and mobile) to connect to a room via a URL parameter.
    *   Connect an internal AI agent to the room that can listen and speak naturally in real time.

### Phase 2: User Interface & Video (The "Zoom" Experience)
*   **Goal:** Build the visual conferencing experience.
*   **Tasks:**
    *   Implement the video grid UI.
    *   Add user controls (mute mic, disable camera).
    *   Add a visual indicator for when the AI agent is "listening" vs "speaking".

### Phase 3: External Agents & Production Readiness
*   **Goal:** Open the platform to external agents and deploy.
*   **Tasks:**
    *   Implement SIP or headless API gateway for outside agents joining via link.
    *   Backend Dockerization.
    *   Deploy Web app and submit to Apple App Store / Google Play Console.