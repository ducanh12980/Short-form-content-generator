# System Architecture & Technical Specification: AI-Generated Shorts Engine

## 1. Project Brief & Strategic Goal

The **AI-Generated Shorts System** is an automated, modular content production pipeline designed to build, scale, and optimize a short-form video channel across distribution networks like TikTok, Instagram Reels, and YouTube Shorts.

*   **The Ultimate Goal:** To systematically streamline the creation of high-retention, faceless short videos featuring Text-to-Speech (TTS) and dynamic live subtitles. Rooted heavily in the principles outlined in [content-learning-system.md](../domain/content-learning-system.md), the system's structural design feeds directly into a continuous optimization feedback loop, ensuring that **"video #100 is always better than video #10."**
*   **The Development Principle:** **Strict Modular Decoupling.** Every component operates as an independent micro-service or functional module driven entirely by explicit data schemas. No creative assets, platform credentials, or prompt logic systems are hardcoded, allowing the operator to substitute any individual element with a superior AI model or specialized API (e.g., swapping a free open-source tool for a premium enterprise engine) without refactoring the core rendering architecture.

---

## 2. Infrastructure Setup & Hybrid Orchestration

To maximize efficiency, maintain low operational overhead, and allow flexible performance tuning, the system splits its execution workflow between a programmatic media engine and a visual cloud manager.
