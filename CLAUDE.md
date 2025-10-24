# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

Personal academic website for Jeremias Klaeui (post-doc in Economics at CREST/ENSAE and ETH Zurich) built with Jekyll and hosted on GitHub Pages. Uses jekyll-theme-minimal.

## Commands

Since Jekyll is a Ruby-based static site generator, the site requires Ruby and bundler. However, no Gemfile exists in the repository currently, suggesting deployment is handled via GitHub Pages directly.

For local development with Jekyll:
```bash
# Serve the site locally (if Gemfile exists)
bundle exec jekyll serve

# Build the site
bundle exec jekyll build
```

## High-level Architecture

### Content Structure
- `index.md`: Homepage with research papers featuring JavaScript-powered abstract toggles
  - toggleAbstract() function shows/hides research paper abstracts
  - Google Analytics tracking for abstract views (gtag events)
- `download/`: Research papers as PDFs
- Static assets: CV (cv_klaeui.pdf), photos, logos

### Theme and Styling
- Base theme: jekyll-theme-minimal (configured in _config.yml)
- Custom styles cascade through:
  1. `_sass/jekyll-theme-minimal.scss`: Modified theme base (Noto Sans font, uppercase headers)
  2. `assets/css/style.scss`: Imports theme and adds custom rules
- Color scheme: #111111 (dark text), #90b8ba accents
- Typography: Gordita for headers, Noto Sans for body

### Template System
- `_layouts/default.html`: Main template with:
  - Font Awesome icons for email/CV links
  - Google Analytics (G-BJ035WTGEJ)
  - Responsive wrapper (960px max width)
  - Sidebar with photo, contact info, CV download