# PixelArt Image Editor

![PixelArt Editor Banner](https://raw.githubusercontent.com/renejr/ied/main/docs/images/banner.png)

## 📋 Overview

PixelArt Image Editor is a modern, feature-rich desktop application built with Python for viewing, navigating, and editing image files with a focus on pixel art. The application provides an intuitive dark-themed interface with powerful image manipulation capabilities.

## ✨ Key Features

- **Modern UI**: Clean, dark-themed interface built with CustomTkinter
- **Image Navigation**: Easily browse through all images in a folder
- **Advanced Viewing Options**:
  - Multiple zoom levels with mouse wheel support
  - Fit to width/height/screen options
  - Image panning with mouse drag
- **Thumbnail Browser**: View all images in the current folder as thumbnails
- **State Persistence**: Remembers zoom level and position for each image
- **Multi-format Support**: Works with PNG, JPG, JPEG, WebP, BMP, TIFF, GIF, and ICO files

## 🖼️ Screenshots

![Main Interface](https://raw.githubusercontent.com/renejr/ied/main/docs/images/main_interface.png)
*Main application interface with an image loaded*

![Thumbnails View](https://raw.githubusercontent.com/renejr/ied/main/docs/images/thumbnails.png)
*Thumbnail browser showing all images in the current folder*

## 🚀 Installation
pip install -r requirements.txt
python app_editor_pixelart.py

### Prerequisites
- Python 3.7+
- Pip package manager

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/renejr/ied.git
   cd ied
   ```
## 🔧 Usage Guide
### Basic Navigation
- Open Image : Click "📂 Abrir imagem" or use the file menu
- Navigate Images : Use "⬅ Anterior" and "Próxima ➡" buttons or keyboard shortcuts
- Zoom : Use mouse wheel, Ctrl+Plus/Minus, or zoom buttons
- Pan : Click and drag to move around the image
### Viewing Options
- Fit to Width : Scales the image to fit the window width
- Fit to Height : Scales the image to fit the window height
- Fit to Screen : Scales the image to fit both dimensions
### Thumbnails
- Press "T" or click the "🖼 Miniaturas" button to open the thumbnail browser
- Click on any thumbnail to load that image
### Saving Images
- Save : Saves changes to the current file
- Save As : Saves the current image to a new file with format options
## 🧩 Technical Details
### Architecture
The application is built with a modular architecture:

- UI Layer : Built with CustomTkinter for a modern look and feel
- Image Processing : Powered by Pillow (PIL) for image manipulation
- Data Layer : SQLite database for storing preferences and view states
### Database Features
- Versioned schema with automatic migrations
- Stores per-image view states (zoom, position)
- Tracks image access history
- Manages application preferences
## 🤝 Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch ( git checkout -b feature/amazing-feature )
3. Commit your changes ( git commit -m 'Add some amazing feature' )
4. Push to the branch ( git push origin feature/amazing-feature )
5. Open a Pull Request
## 📄 License
This project is licensed under the MIT License - see the LICENSE file for details.

## 📞 Contact
René Junior - @renejr

Project Link: https://github.com/renejr/ied