# Discord Bot Setup Guide

## Prerequisites
- Python 3.11+ installed
- Discord Bot Token
- Environment variables configured

## Installation Steps

### 1. Create Virtual Environment
```bash
python3 -m venv venv
```

### 2. Activate Virtual Environment
```bash
# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
pip install python-dotenv
```

### 4. Create Environment File
Copy the environment template and configure it:

```bash
# Copy the template
cp env_template.txt .env

# Edit the .env file with your Discord bot token
# All channel IDs are pre-configured but can be modified if needed
```

### 5. Run the Bot
```bash
python fractored-mirror-bot.py
```

## Features
- **Deal Processing**: Automatically processes deal posts and creates rich embeds
- **Multiple Image Support**: Handles multiple images from attachments, embeds, and URLs
- **Channel Routing**: Routes deals to appropriate channels (major, minor, member, food)
- **Image Watermarking**: Adds watermarks to images in success channel
- **Edit Capabilities**: Allows editing of deal embeds with Edit/Advanced buttons

## Notes
- Make sure your bot has the necessary permissions in your Discord server
- The bot requires message content intent to be enabled
- All channel IDs should be valid Discord channel IDs 