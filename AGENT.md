# AGENT.md

## Project Overview

This project builds a **Senior iOS Knowledge Tree** for learning,
interview preparation, and technical reference.

The detailed list of topics and hierarchy is defined in:

**Senior-iOS-Knowledge-Tree.md**

AI coding assistants must use that file as the **single source of
truth** for the knowledge hierarchy and section organization.

The generated learning system will power:

-   a **static documentation website**
-   a **mobile learning app**
-   a **structured knowledge base for AI tools**
-   a **technical interview preparation platform**

The project follows this pipeline:

Markdown Content\
↓\
Static Generator\
↓\
HTML Pages\
↓\
Website + Mobile App

The system must remain **simple, maintainable, and scalable**.

------------------------------------------------------------------------

# Core Principles

1.  **Content-first architecture**
2.  **Markdown is the source of truth**
3.  **HTML is generated automatically**
4.  **Minimal styling and dependencies**
5.  **Strict knowledge hierarchy**
6.  **Easy to convert into mobile apps (WebView)**

Avoid heavy frameworks unless absolutely necessary.

------------------------------------------------------------------------

# Knowledge Tree Source

The knowledge structure is defined in:

`Senior-iOS-Knowledge-Tree.md`

AI assistants must:

-   read the hierarchy from this file
-   generate folders and pages accordingly
-   maintain the same naming and ordering

This ensures consistency across the system.

------------------------------------------------------------------------

# Repository Structure

    ios-knowledge-tree/
    │
    ├── AGENT.md
    ├── README.md
    ├── Senior-iOS-Knowledge-Tree.md
    │
    ├── content/                # Markdown learning content
    │   ├── 01-swift-language/
    │   │   ├── index.md
    │   │   ├── value-vs-reference.md
    │   │   └── copy-on-write.md
    │   │
    │   ├── 02-memory-management/
    │   │   ├── index.md
    │   │   └── arc.md
    │   │
    │   └── ...
    │
    ├── templates/              # HTML templates
    │   ├── topic.html
    │   └── section.html
    │
    ├── components/             # reusable UI components
    │   ├── header.html
    │   ├── navigation.html
    │   └── footer.html
    │
    ├── assets/
    │   └── style.css
    │
    ├── scripts/                # build scripts
    │   └── generate_site.py
    │
    └── site/                   # generated static website

**Important:**

The `/site` folder is **generated automatically** and must **never be
edited manually**.

------------------------------------------------------------------------

# Content Format (Markdown)

Each topic must follow the exact structure below.

    # Topic Title

    ## 1. Overview

    Short explanation describing what the concept is and why it exists.

    ## 2. Simple Explanation

    Explain the concept in beginner-friendly language.

    ## 3. Deep iOS Knowledge

    Describe implementation details, runtime behavior, performance implications, and internal mechanisms.

    ## 4. Practical Usage

    Provide real Swift examples or architecture examples.

    ## 5. Interview Questions & Answers

    ### Basic
    Question + short answer.

    ### Hard
    More advanced engineering-level questions.

    ### Expert
    Senior-level or architecture-level questions.

    ## 6. Common Issues & Solutions

    Describe real-world problems engineers encounter and how to fix them.

    ## 7. Related Topics

    Link to other Markdown files inside the project.

Every topic file must strictly follow this structure.

------------------------------------------------------------------------

# HTML Generation

Markdown files are converted into HTML pages using a static generation
script.

The generator must:

1.  Scan the `/content` directory
2.  Convert Markdown → HTML
3.  Apply HTML templates
4.  Inject navigation components
5.  Output pages to `/site`

Example output:

    site/
    ├── swift-language/
    │   ├── index.html
    │   └── value-vs-reference.html
    │
    ├── concurrency/
    │   └── actors.html

The structure of `/site` should **mirror the `/content` structure**.

------------------------------------------------------------------------

# HTML Template Requirements

Templates must be:

-   extremely simple
-   semantic HTML
-   minimal CSS
-   mobile friendly
-   easy to load in WebView

Example sections:

    <h1>Topic Title</h1>

    <h2>Overview</h2>
    <h2>Simple Explanation</h2>
    <h2>Deep iOS Knowledge</h2>
    <h2>Practical Usage</h2>
    <h2>Interview Questions</h2>
    <h2>Common Issues</h2>
    <h2>Related Topics</h2>

Avoid JavaScript-heavy frameworks.

------------------------------------------------------------------------

# Navigation Rules

Each page should allow navigation to:

-   homepage
-   parent section
-   related topics

Use **relative links** whenever possible.

------------------------------------------------------------------------

# CSS Rules

CSS must remain minimal.

Goals:

-   readability
-   fast loading
-   mobile compatibility

Avoid UI frameworks like Bootstrap unless required.

------------------------------------------------------------------------

# Script Responsibilities

The build script should:

1.  scan `/content`
2.  convert Markdown → HTML
3.  apply templates
4.  copy static assets
5.  generate `/site` output

The build process must be **deterministic and reproducible**.

------------------------------------------------------------------------

# Rules for AI Coding Assistants

When modifying or extending the project:

1.  Never manually edit `/site` files.
2.  Always modify Markdown in `/content`.
3.  Follow the topic template strictly.
4.  Maintain the hierarchy defined in `Senior-iOS-Knowledge-Tree.md`.
5.  Keep templates simple.
6.  Avoid unnecessary dependencies.

------------------------------------------------------------------------

# Long-Term Vision

This project may later support:

-   interactive roadmap UI
-   search functionality
-   AI-powered interview trainer
-   mobile learning app
-   developer knowledge graph

Therefore all content must remain:

-   **structured**
-   **machine-readable**
-   **consistent**

------------------------------------------------------------------------

# Summary

The system follows a clear pipeline:

Markdown Content\
↓\
Static Generator\
↓\
HTML Website\
↓\
Mobile Learning App

All content must remain **clean, structured, and scalable**.
