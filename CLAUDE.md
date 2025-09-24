# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a personal academic website built with Jekyll and hosted on GitHub Pages. The site uses the jekyll-theme-minimal theme and showcases research papers, publications, and professional information for Jeremias Klaeui, a post-doc in Economics at CREST in Paris.

## Commands

### Local Development

Since Jekyll is a Ruby-based static site generator, use bundle to manage dependencies and serve the site:

```bash
# Install dependencies (first time setup)
bundle install

# Serve the site locally with auto-reload
bundle exec jekyll serve

# Build the site for production
bundle exec jekyll build
```

The site will be available at `http://localhost:4000` when running locally.

## Site Architecture

### Key Files and Directories

- `_config.yml`: Main Jekyll configuration (theme, title, logo, Google Analytics)
- `index.md`: Homepage content with research papers and bio (uses Markdown with embedded HTML/JavaScript for interactive abstract toggles)
- `_layouts/`: HTML templates
  - `default.html`: Main layout with header, navigation, and Google Analytics
- `_sass/`: SCSS stylesheets 
  - `jekyll-theme-minimal.scss`: Main theme styles with custom colors (#00cc99 for headings, #507DBC for hover)
- `assets/css/style.scss`: Entry point for custom styles (imports theme and adds custom rules)
- `download/`: PDF papers and research documents

### Interactive Features

The site includes JavaScript-powered abstract toggles for research papers:
- Abstracts are hidden by default with `display: none`
- `toggleAbstract()` function in index.md toggles visibility
- Custom button styling with green (#00cc99) background
- Google Analytics events track abstract views

### Styling Conventions

- Primary color: #00cc99 (teal green) for headings and buttons
- Hover color: #507DBC (blue)
- Font: Noto Sans
- Layout: 960px wrapper with 270px sidebar and 600px content area
- Responsive breakpoints at 960px, 720px, and 480px