from flask import Flask, render_template, jsonify
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
from plotly.utils import PlotlyJSONEncoder
import os
from datetime import datetime
import numpy as np

app = Flask(__name__)

# File paths
GYM_DATA_FILE = "gym_workout_data.csv"

def load_gym_data():
    """Load and process gym workout data"""
    if not os.path.exists(GYM_DATA_FILE):
        return None

    df = pd.read_csv(GYM_DATA_FILE)
    df['date'] = pd.to_datetime(df['date'])
    df['muscle_group'] = df['workout'].str.extract(r'(\d+)\.\s*(.+)')[1]
    return df

def get_progress_data(df, exercise_name):
    """Get progress data for a specific exercise"""
    exercise_data = df[df['exercise'] == exercise_name].copy()

    # Group by date and calculate metrics
    daily_progress = exercise_data.groupby('date').agg({
        'weight': ['max', 'mean'],
        'reps': ['max', 'sum'],
        'volume': 'sum'
    }).round(2)

    # Flatten column names
    daily_progress.columns = ['max_weight', 'avg_weight', 'max_reps', 'total_reps', 'total_volume']
    daily_progress = daily_progress.reset_index()

    return daily_progress

def create_volume_trend_chart(df):
    """Create volume trend chart over time"""
    daily_volume = df.groupby(['date', 'workout'])['volume'].sum().reset_index()

    fig = px.line(daily_volume, x='date', y='volume', color='workout',
                  title='Training Volume Over Time',
                  labels={'volume': 'Volume (lbs × reps)', 'date': 'Date'},
                  template='plotly_white')

    fig.update_layout(
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    return json.dumps(fig, cls=PlotlyJSONEncoder)

def create_muscle_group_comparison(df):
    """Create muscle group volume comparison"""
    muscle_volume = df.groupby('workout')['volume'].sum().reset_index()
    muscle_volume['workout'] = muscle_volume['workout'].str.replace(r'^\d+\.\s*', '', regex=True)

    fig = px.bar(muscle_volume, x='workout', y='volume',
                 title='Total Volume by Muscle Group',
                 labels={'volume': 'Total Volume (lbs × reps)', 'workout': 'Muscle Group'},
                 template='plotly_white',
                 color='volume',
                 color_continuous_scale='viridis')

    fig.update_layout(height=400, showlegend=False)

    return json.dumps(fig, cls=PlotlyJSONEncoder)

def create_exercise_progress_chart(df, exercise_name):
    """Create progress chart for a specific exercise"""
    progress_data = get_progress_data(df, exercise_name)

    if progress_data.empty:
        return None

    fig = go.Figure()

    # Add max weight line
    fig.add_trace(go.Scatter(
        x=progress_data['date'],
        y=progress_data['max_weight'],
        mode='lines+markers',
        name='Max Weight',
        line=dict(color='#1f77b4', width=3),
        marker=dict(size=8)
    ))

    # Add volume bars (secondary y-axis)
    fig.add_trace(go.Bar(
        x=progress_data['date'],
        y=progress_data['total_volume'],
        name='Total Volume',
        opacity=0.6,
        yaxis='y2',
        marker_color='#ff7f0e'
    ))

    fig.update_layout(
        title=f'{exercise_name} - Progress Over Time',
        xaxis_title='Date',
        yaxis=dict(title='Weight (lbs)', side='left'),
        yaxis2=dict(title='Volume (lbs × reps)', side='right', overlaying='y'),
        template='plotly_white',
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    return json.dumps(fig, cls=PlotlyJSONEncoder)

def create_workout_frequency_chart(df):
    """Create workout frequency chart"""
    workout_freq = df.groupby([df['date'].dt.to_period('W'), 'workout']).size().unstack(fill_value=0)
    workout_freq.index = workout_freq.index.to_timestamp()

    fig = go.Figure()

    colors = ['#1f77b4', '#ff7f0e', '#2ca02c']
    for i, workout in enumerate(workout_freq.columns):
        fig.add_trace(go.Bar(
            x=workout_freq.index,
            y=workout_freq[workout],
            name=workout.replace(r'^\d+\.\s*', ''),
            marker_color=colors[i % len(colors)]
        ))

    fig.update_layout(
        title='Weekly Workout Frequency',
        xaxis_title='Week',
        yaxis_title='Number of Workouts',
        barmode='stack',
        template='plotly_white',
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    return json.dumps(fig, cls=PlotlyJSONEncoder)

@app.route('/')
def dashboard():
    """Main dashboard page"""
    df = load_gym_data()

    if df is None:
        return render_template('error.html',
                             message="No workout data found. Please run the gym analyzer first.")

    # Calculate summary statistics
    total_workouts = df.groupby(['date', 'workout']).ngroups
    total_volume = df['volume'].sum()
    date_range = f"{df['date'].min().strftime('%B %d, %Y')} - {df['date'].max().strftime('%B %d, %Y')}"
    top_exercises = df['exercise'].value_counts().head(5).to_dict()

    # Create charts
    volume_chart = create_volume_trend_chart(df)
    muscle_group_chart = create_muscle_group_comparison(df)
    frequency_chart = create_workout_frequency_chart(df)

    return render_template('dashboard.html',
                         total_workouts=total_workouts,
                         total_volume=f"{total_volume:,}",
                         date_range=date_range,
                         top_exercises=top_exercises,
                         volume_chart=volume_chart,
                         muscle_group_chart=muscle_group_chart,
                         frequency_chart=frequency_chart)

@app.route('/exercises')
def exercises():
    """Exercise analysis page"""
    df = load_gym_data()

    if df is None:
        return render_template('error.html',
                             message="No workout data found. Please run the gym analyzer first.")

    # Get exercise list with stats
    exercise_stats = df.groupby('exercise').agg({
        'volume': 'sum',
        'weight': 'max',
        'date': ['min', 'max', 'nunique']
    }).round(2)

    exercise_stats.columns = ['total_volume', 'max_weight', 'first_date', 'last_date', 'workout_count']
    exercise_stats = exercise_stats.reset_index()
    exercise_stats = exercise_stats.sort_values('total_volume', ascending=False)

    return render_template('exercises.html', exercise_stats=exercise_stats.to_dict('records'))

@app.route('/exercise/<exercise_name>')
def exercise_detail(exercise_name):
    """Detailed view for a specific exercise"""
    df = load_gym_data()

    if df is None:
        return render_template('error.html',
                             message="No workout data found. Please run the gym analyzer first.")

    exercise_data = df[df['exercise'] == exercise_name]

    if exercise_data.empty:
        return render_template('error.html',
                             message=f"No data found for exercise: {exercise_name}")

    # Create progress chart
    progress_chart = create_exercise_progress_chart(df, exercise_name)

    # Calculate statistics
    stats = {
        'total_sets': len(exercise_data),
        'total_volume': exercise_data['volume'].sum(),
        'max_weight': exercise_data['weight'].max(),
        'max_reps': exercise_data['reps'].max(),
        'avg_weight': exercise_data[exercise_data['weight'] > 0]['weight'].mean(),
        'first_workout': exercise_data['date'].min().strftime('%B %d, %Y'),
        'last_workout': exercise_data['date'].max().strftime('%B %d, %Y'),
        'workout_count': exercise_data['date'].nunique()
    }

    # Recent performance (last 5 workouts)
    recent_workouts = exercise_data.groupby('date').agg({
        'weight': 'max',
        'reps': 'max',
        'volume': 'sum'
    }).tail(5).reset_index()
    recent_workouts['date'] = recent_workouts['date'].dt.strftime('%B %d, %Y')

    return render_template('exercise_detail.html',
                         exercise_name=exercise_name,
                         stats=stats,
                         progress_chart=progress_chart,
                         recent_workouts=recent_workouts.to_dict('records'))

@app.route('/muscle-groups')
def muscle_groups():
    """Muscle group analysis page"""
    df = load_gym_data()

    if df is None:
        return render_template('error.html',
                             message="No workout data found. Please run the gym analyzer first.")

    # Calculate muscle group statistics
    muscle_stats = df.groupby('workout').agg({
        'volume': 'sum',
        'date': 'nunique',
        'exercise': 'nunique'
    }).round(2)

    muscle_stats.columns = ['total_volume', 'workout_count', 'exercise_count']
    muscle_stats = muscle_stats.reset_index()
    muscle_stats['muscle_group'] = muscle_stats['workout'].str.replace(r'^\d+\.\s*', '', regex=True)

    # Get top exercises for each muscle group
    muscle_group_exercises = {}
    for workout in df['workout'].unique():
        top_exercises = df[df['workout'] == workout].groupby('exercise')['volume'].sum().sort_values(ascending=False).head(3)
        muscle_group_exercises[workout] = top_exercises.to_dict()

    return render_template('muscle_groups.html',
                         muscle_stats=muscle_stats.to_dict('records'),
                         muscle_group_exercises=muscle_group_exercises)

@app.route('/api/exercise-progress/<exercise_name>')
def api_exercise_progress(exercise_name):
    """API endpoint for exercise progress data"""
    df = load_gym_data()

    if df is None:
        return jsonify({'error': 'No data available'})

    progress_data = get_progress_data(df, exercise_name)

    if progress_data.empty:
        return jsonify({'error': 'No data for this exercise'})

    # Convert to JSON-serializable format
    progress_data['date'] = progress_data['date'].dt.strftime('%Y-%m-%d')

    return jsonify(progress_data.to_dict('records'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
