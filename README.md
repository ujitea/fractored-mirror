<h1 align="center">FRACTORED-MIRROR</h1>

<p align="center">
  <em>Transforming Ideas into Seamless Digital Experiences</em>
</p>

<p align="center">
  <a href="https://github.com/ujitea/fractored-mirror/commits/main">
    <img alt="Last commit" src="https://img.shields.io/github/last-commit/ujitea/fractored-mirror?logo=github">
  </a>
  <img alt="Python" src="https://img.shields.io/badge/python-3.10%2B-blue">
  <img alt="Languages" src="https://img.shields.io/github/languages/count/ujitea/fractored-mirror">
</p>

<p align="center">
  Built with the tools and technologies:
</p>

<p align="center">
  <img alt="Markdown" src="https://img.shields.io/badge/MD-Markdown-informational">
  <img alt="Python" src="https://img.shields.io/badge/Python-🐍-blue">
</p>

---

## Table of Contents

- [Overview](#overview)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Usage](#usage)
  - [Testing](#testing)
- [Configuration](#configuration)
- [Features](#features)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Overview

**fractored-mirror** is a developer toolkit that bridges **trading automation** with **dynamic content management in Discord**. It enables seamless execution of deal strategies, workflow routing, and engaging content sharing—while maintaining visual branding and moderation controls.

### Why fractored-mirror?

`fractored-mirror` is a **mirroring service**: it listens to designated source channels, **parses text**, and **forwards a clean, normalized embed** to a centralized **main server/channel**—reliably and with guardrails.

- 🔁 **Mirroring pipeline**: multi-channel intake → parse → normalize (price/links/images) → forward to main.
- 🧠 **Smart parsing**: extracts title/link/price/ATC/image, waits briefly for Discord previews, and builds consistent embeds.
- 🎛️ **Deterministic routing**: one-click buttons (major/minor/member/personal/food) send to the correct destination.
- ⏱️ **Throttling & retries**: per-destination rate limiting with exponential backoff to survive transient HTTP/429s.
- 🖼️ **Optional watermarking**: images can be branded before they’re mirrored to the main channel.
- 🔐 **Configurable**: all IDs and tokens via `.env`; easy to run in different servers/environments.

---

## Getting Started

### Prerequisites
- Python **3.10+**
- A Discord **Bot** with:
  - Scopes: `bot`, `applications.commands`
  - Permissions: `Send Messages`, `Embed Links`, `Attach Files`, (optional) `Manage Messages` for watermark flow
- (Recommended) Git + virtualenv

### Installation
```bash
# Clone
git clone https://github.com/ujitea/fractored-mirror.git
cd fractored-mirror

# Virtual env
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

# Install deps
pip install -r requirements.txt
