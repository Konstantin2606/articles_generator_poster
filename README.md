# ArtGenPost

**ArtGenPost** is a desktop application that automatically generates SEO-optimized articles using the GPT API and publishes them to WordPress websites. The application provides a user-friendly graphical interface based on PyQt6 for configuring article generation and publishing settings.


## Key Features

- Generate SEO-optimized articles using GPT models.
- Publish articles to WordPress websites with the ability to upload images.
- User-friendly interface for managing article generation and publishing parameters.
- Batch publishing with pauses between batches.
- Track already published articles using an SQLite database.

## Requirements

The zipped package includes the pre-built application, making setup quick and straightforward. To use the application, you’ll need:

- GPT API Key: For generating article content (platform.openai.com/api-keys).
- Pixabay API Key: For adding images to articles (pixabay - explore - API - Get Started OR pixabay.com/api/docs/ - Parameters).
- WordPress Site: REST API must be activated (Wordpress - Users - All Users - User(admin) - Application Passwords)

## Installation

- Download and unzip the package from the repository.
- Locate the examples folder, which includes sample prompts, API key files, and file structures needed to configure the application.

## Usage

- Launch the application from the unzipped folder.
- Configure your prompts, API keys, and WordPress settings using the settings interface.
- Start generating and posting articles.

## License

Licensed under Apache-2.0.