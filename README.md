# Strava Gym Analyzer

A Flask web application that analyzes your Strava gym activities and provides detailed insights into your workout progress. This app specifically tracks structured gym routines including Chest/Shoulders/Triceps, Back/Biceps, and Legs/Abs workouts.

## Features

- **Strava Integration**: Fetches your gym activities directly from Strava
- **Workout Analysis**: Analyzes specific gym routines and tracks progress over time
- **Interactive Dashboard**: Web-based interface with charts and visualizations
- **Progress Tracking**: Monitor improvements in sets, reps, and workout consistency
- **Exercise Details**: Detailed breakdowns of individual exercises and muscle groups

## Prerequisites

- Python 3.7 or higher
- A Strava account with gym activities
- Strava API application (Client ID and Client Secret)

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd strava_analyzer
```

### 2. Install Dependencies

```bash
pip install flask pandas plotly matplotlib requests python-dotenv
```

### 3. Set Up Strava API

1. Go to [Strava's Developer Portal](https://www.strava.com/settings/api)
2. Create a new application
3. Note down your **Client ID** and **Client Secret**
4. Set the **Authorization Callback Domain** to `localhost` (for local development)

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```bash
touch .env
```

Add your Strava API credentials to the `.env` file:

```env
STRAVA_CLIENT_ID=your_client_id_here
STRAVA_CLIENT_SECRET=your_client_secret_here
```

### 5. Initial Authentication

Run the token fetcher to authenticate with Strava:

```bash
python fetch_tokens.py
```

This will:
- Open your browser for Strava authentication
- Save your access tokens securely
- Create the initial `strava_tokens.json` file

### 6. Fetch and Analyze Your Data

Run the gym analyzer to fetch your activities:

```bash
python gym_analyzer.py
```

This will:
- Download all your Strava activities
- Filter and analyze gym workouts
- Generate progress charts
- Create the `gym_workout_data.csv` file

### 7. Start the Web Application

```bash
python app.py
```

The application will start on `http://localhost:5000`

## Usage

### Web Interface

1. **Dashboard**: Overview of your gym progress with interactive charts
2. **Muscle Groups**: Detailed analysis of different muscle group workouts
3. **Exercises**: Individual exercise breakdowns and progress tracking
4. **Exercise Details**: Deep dive into specific exercises with historical data

### Supported Workout Types

The app currently analyzes these specific gym routines:
- **1. Chest Shoulders and Triceps**
- **2. Back and Biceps**
- **3. Legs and Abs**

Make sure your Strava activities use these exact titles for proper analysis.

### Data Refresh

To update your data with new workouts:

```bash
python gym_analyzer.py
```

Then restart the Flask app to see the latest data.

## File Structure

```
strava_analyzer/
├── app.py                          # Main Flask application
├── gym_analyzer.py                 # Data fetching and analysis
├── strava_auth_manager.py          # Strava authentication handling
├── fetch_tokens.py                 # Initial token setup
├── templates/                      # HTML templates
│   ├── base.html
│   ├── dashboard.html
│   ├── exercises.html
│   └── ...
├── static/                         # CSS and JS files
├── gym_workout_data.csv           # Generated workout data (ignored by git)
├── strava_activities.json         # Raw Strava data (ignored by git)
├── strava_tokens.json             # API tokens (ignored by git)
└── README.md
```

## Troubleshooting

### Authentication Issues

- Ensure your Strava app settings allow `localhost` as a callback domain
- Check that your Client ID and Client Secret are correct in the `.env` file
- Try running `fetch_tokens.py` again if authentication fails

### No Data Showing

- Make sure your Strava activities use the exact workout titles listed above
- Run `gym_analyzer.py` to refresh your data
- Check that `gym_workout_data.csv` was created and contains data

### Missing Dependencies

Install missing packages:
```bash
pip install <package_name>
```

Common packages: `flask pandas plotly matplotlib requests python-dotenv`

## Privacy and Security

- Your Strava tokens and personal data are stored locally only
- The `.gitignore` file prevents sensitive data from being committed to version control
- Never share your `strava_tokens.json` or `.env` files

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is for personal use. Make sure to comply with Strava's API Terms of Service.
