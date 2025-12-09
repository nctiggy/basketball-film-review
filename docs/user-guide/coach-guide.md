# Coach Guide

This guide covers all features available to coaches in the Basketball Film Review application.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Managing Teams](#managing-teams)
3. [Managing Your Roster](#managing-your-roster)
4. [Uploading Game Videos](#uploading-game-videos)
5. [Creating Clips](#creating-clips)
6. [Drawing Annotations](#drawing-annotations)
7. [Recording Voice-Over](#recording-voice-over)
8. [Assigning Clips to Players](#assigning-clips-to-players)
9. [Entering Game Statistics](#entering-game-statistics)
10. [Viewing Player Progress](#viewing-player-progress)

## Getting Started

### Signing In

1. Navigate to the application URL provided by your administrator
2. Click "Sign in with Google"
3. Select your Google account
4. Your coach account will be created automatically on first sign-in

Your coach account gives you full access to create teams, manage players, and share film.

## Managing Teams

### Creating a Team

1. After signing in, click "Create Team" or navigate to the Teams section
2. Enter your team information:
   - **Team Name**: E.g., "Eastside Tigers"
   - **Season**: E.g., "Fall 2024" or "2024-2025"
3. Click "Create Team"

You will automatically be added as the head coach for the team.

### Viewing Your Teams

All teams where you are a coach appear in your Teams list. Click on any team to manage it.

### Editing Team Details

1. Select a team from your Teams list
2. Click "Edit Team"
3. Update the team name or season
4. Click "Save Changes"

### Deleting a Team

Only the team creator can delete a team. Deleting a team will:
- Remove all players from the roster
- Delete all games and clips associated with the team
- This action cannot be undone

To delete:
1. Select the team
2. Click "Delete Team"
3. Confirm the deletion

### Adding Assistant Coaches

1. Select your team
2. Go to the "Coaches" tab
3. Click "Add Coach"
4. Enter the coach's email address
5. Select their role:
   - **Head Coach**: Can add/remove players and other coaches
   - **Assistant Coach**: Can view and create content but cannot manage coaches
6. Click "Add"

The coach must have already created an account by signing in with Google.

### Removing Coaches

1. Go to the team's "Coaches" tab
2. Find the coach you want to remove
3. Click "Remove"
4. Confirm the action

Note: You cannot remove the last coach from a team.

## Managing Your Roster

### Adding Players to Your Team

Method 1: Create Player and Generate Invite
1. Select your team
2. Go to the "Roster" tab
3. Click "Add Player"
4. Fill in player information:
   - **Name**: Player's full name
   - **Jersey Number** (optional)
   - **Position** (optional): PG, SG, SF, PF, C
   - **Graduation Year** (optional)
5. Click "Create Player"

An invite code will be generated automatically. Share this code with the player so they can set up their account.

### Sharing Player Invite Links

After creating a player:
1. Copy the invite code shown
2. Share it with the player via:
   - Text message
   - Email
   - In person

The player will use this code to:
- Create their username and password
- Access their assigned clips
- View their statistics

### Generating Parent Invites

Parents can view clips and stats for their linked children:

1. Go to the team's "Roster" tab
2. Find the player
3. Click "Generate Parent Invite"
4. Share the invite code with the parent

Parents use this code to create their account and link to their child.

### Viewing Player Status

Players can have these statuses:
- **Invited**: Player account created but hasn't claimed their invite yet
- **Active**: Player has set up their account and can access the platform
- **Suspended**: Player's access has been temporarily disabled

### Removing Players from Team

1. Go to the "Roster" tab
2. Find the player
3. Click "Remove from Team"
4. Confirm the action

Note: This removes the player from the team but does not delete their account.

## Uploading Game Videos

### Supported Video Formats

The application supports most common video formats:
- MP4 (recommended)
- MOV
- AVI
- Other formats supported by ffmpeg

### Upload Process

1. Navigate to the "Games" section
2. Click "Upload Game"
3. Fill in game information:
   - **Team**: Select the team (required)
   - **Game Name**: E.g., "vs Warriors - Home Game"
   - **Game Date**: Select the date
   - **Home Team Color**: E.g., "white", "red" (for AI analysis)
   - **Away Team Color**: E.g., "dark", "blue" (for AI analysis)
4. Click "Choose File" and select your video
5. Click "Upload"

Upload time depends on:
- Video file size
- Your internet connection speed
- Server processing capacity

Large files (over 1GB) may take several minutes.

### Video Best Practices

For best results:
- Use good quality video (720p or higher recommended)
- Ensure consistent lighting throughout the game
- Film from an elevated position showing the full court
- Use a stable mount (avoid handheld if possible)
- Start recording before tip-off and keep recording until the game ends

### Managing Game Videos

#### Editing Game Details
1. Go to "Games"
2. Click on a game
3. Click "Edit Game"
4. Update game information
5. Click "Save Changes"

#### Deleting Games
Deleting a game will also delete:
- All videos for that game
- All clips created from those videos
- This action cannot be undone

To delete:
1. Select the game
2. Click "Delete Game"
3. Confirm the deletion

## Creating Clips

Clips are short segments extracted from full game videos, perfect for film study.

### Creating a Clip

1. Navigate to the "Clips" section
2. Click "Create Clip"
3. Select the game from the dropdown
4. Enter the clip timing:
   - **Start Time**: Format as `mm:ss` or `hh:mm:ss`
     - Examples: `5:30`, `1:15:20`
   - **End Time**: Use the same format
5. Add tags to categorize the clip:
   - Player names
   - Play types (e.g., "fast break", "zone defense")
   - Outcomes (e.g., "turnover", "made basket")
6. Select players involved (optional)
7. Add notes for context (optional)
8. Click "Create Clip"

### Clip Processing

After creating a clip:
- Status starts as "Pending"
- Changes to "Processing" when extraction begins
- Changes to "Completed" when ready (usually under 30 seconds)
- If it fails, status shows "Failed" with an error message

The clip list refreshes automatically to show updated statuses.

### Timestamp Format

Use these formats for timestamps:
- **Minutes:Seconds**: `5:30` = 5 minutes, 30 seconds
- **Hours:Minutes:Seconds**: `1:15:20` = 1 hour, 15 minutes, 20 seconds

### Organizing Clips with Tags

Tags help you find and organize clips later. Use consistent tag names:

Good examples:
- Player names: "John Smith", "Jane Doe"
- Play types: "fast break", "pick and roll", "zone defense"
- Skills: "rebounding", "passing", "shooting"
- Results: "made basket", "turnover", "good defense"

Tips:
- Use the same tag name consistently ("defense" not "def")
- Use multiple tags per clip for better organization
- The top 5 most-used tags appear as quick-select buttons

### Viewing and Managing Clips

#### Viewing Clips
1. Go to the "Clips" section
2. Filter by:
   - Game
   - Tag
   - Player
3. Click on a clip to view details

#### Editing Clips
1. Select a clip
2. Click "Edit"
3. Update tags, players, notes, or timestamps
4. Click "Save Changes"

#### Deleting Clips
1. Select a clip
2. Click "Delete"
3. Confirm the deletion

## Drawing Annotations

Annotations allow you to highlight specific moments or movements in clips. You can draw shapes, arrows, and add text directly on the video.

### Creating Annotations

1. Open a completed clip
2. Click "Annotate"
3. The annotation canvas appears over the video
4. Use the drawing tools:
   - **Arrow**: Draw arrows to show movement or direction
   - **Circle**: Highlight a player or area
   - **Line**: Draw paths or show spacing
   - **Textbox**: Add labels or notes on the video
5. For each annotation, set:
   - **Start Time**: When the annotation appears
   - **End Time**: When it disappears
   - **Color**: Make it stand out
   - **Stroke Width**: Adjust thickness

### Drawing Tools

**Arrow Tool**
- Click and drag to draw an arrow
- Use it to show:
  - Player movement
  - Pass direction
  - Defensive rotations

**Circle Tool**
- Click and drag to create a circle
- Use it to:
  - Highlight a player
  - Mark an area on the court
  - Draw attention to positioning

**Line/Path Tool**
- Click to add points
- Double-click to finish
- Use it for:
  - Drawing plays
  - Showing cutting lanes
  - Illustrating spacing

**Text Tool**
- Click where you want text
- Type your message
- Use it for:
  - Player names
  - Key points
  - Reminders

### Timing Annotations

Each annotation can appear at a specific time in the clip:
- Set **Start Time** for when it appears
- Set **End Time** for when it disappears
- This lets you show multiple things in sequence
- Players see annotations automatically when they play the clip

### Editing Annotations

1. Open the clip
2. Click "Edit Annotations"
3. Select the annotation to edit
4. Modify properties or delete it
5. Click "Save"

### Best Practices for Annotations

- **Keep it simple**: Don't overcrowd the video
- **Use colors wisely**: Different colors for different players/concepts
- **Time them well**: Show annotations only when relevant
- **Add text sparingly**: Short labels work best
- **Test the clip**: View it as a player would to ensure clarity

## Recording Voice-Over

Voice-over audio helps you provide personal coaching feedback for each clip.

### Recording Audio

1. Open a completed clip
2. Click "Record Audio"
3. Allow microphone access if prompted
4. Click "Start Recording"
5. Speak your coaching points while watching the clip
6. Click "Stop Recording"
7. Preview your audio
8. Click "Save" to attach it to the clip

### Audio Best Practices

- **Use a quiet environment**: Minimize background noise
- **Speak clearly**: Players need to understand you
- **Be specific**: Reference what's happening on screen
- **Stay positive**: Even when correcting, use constructive language
- **Keep it concise**: Focus on 1-3 key points per clip
- **Watch as you record**: This helps you time your comments with the action

### What to Include in Voice-Over

Good coaching audio often includes:
- What the player did well
- What could be improved
- Specific techniques or footwork
- What to watch for in this situation
- How it relates to practice

Example: "Great job staying low on defense here. Notice how you keep your hands active and force him baseline. Next time, try to cut him off one step earlier so he has even less space."

### Managing Audio

- **Re-record**: Click "Record Audio" again to replace existing audio
- **Delete**: Remove audio by clicking "Delete Audio"
- **Preview**: Listen before saving to ensure good quality

## Assigning Clips to Players

Once a clip is ready, you can assign it to specific players.

### Assigning a Clip

1. Go to the "Clips" section
2. Select a clip (must be "Completed" status)
3. Click "Assign to Players"
4. Select one or more players from the list
5. Optionally add:
   - **Message**: Personal note for the player
   - **Priority**:
     - High: Urgent review needed
     - Normal: Regular film study
     - Low: Optional viewing
6. Click "Assign"

### Assignment Options

**Message**
Add a personal message to the assignment:
- "Great defense in this play!"
- "Watch how you position yourself here"
- "Let's work on this in practice"

**Priority Levels**
- **High**: Shows at the top of player's list, indicates urgency
- **Normal**: Standard assignment
- **Low**: For extra credit or optional viewing

### Managing Assignments

#### Viewing Assignments
1. Select a clip
2. Click "View Assignments"
3. See which players have:
   - Not viewed it yet
   - Viewed it
   - Acknowledged they've reviewed it

#### Removing Assignments
1. Go to clip assignments
2. Find the player
3. Click "Remove Assignment"
4. Confirm

This removes the clip from that player's view.

### Assignment Best Practices

- **Assign relevant clips**: Only send clips where the player appears or can learn
- **Add context**: Use the message field to explain why they're watching
- **Set priorities**: Use high priority sparingly for maximum impact
- **Follow up**: Check if players have viewed and acknowledged clips
- **Discuss in practice**: Reference clips during practice for reinforcement

## Entering Game Statistics

Track player performance across games with detailed statistics.

### Adding Stats for a Game

1. Navigate to "Games"
2. Select a game
3. Click "Enter Stats"
4. For each player on your roster, enter:

**Scoring**
- Points
- Field Goals Made / Attempted
- 3-Pointers Made / Attempted
- Free Throws Made / Attempted

**Rebounds**
- Offensive Rebounds
- Defensive Rebounds

**Other Stats**
- Assists
- Steals
- Blocks
- Turnovers
- Fouls
- Minutes Played

5. Click "Save Stats"

### Editing Existing Stats

1. Go to the game
2. Click "Edit Stats"
3. Update the numbers
4. Click "Save"

Stats are updated, not duplicated.

### Bulk Entry Tips

- Enter stats during or right after the game for accuracy
- Use the tab key to move quickly between fields
- Double-check totals before saving
- You can save partial data and come back later

### Stats Validation

The system calculates:
- Field Goal Percentage
- 3-Point Percentage
- Free Throw Percentage
- Total Rebounds (Offensive + Defensive)
- Points should match (2×FGM) + (3×3PM) + FTM

If numbers don't add up, you'll see a warning.

## Viewing Player Progress

### Individual Player Stats

1. Go to "Roster"
2. Click on a player
3. View their dashboard with:
   - **Season Averages**: Points, rebounds, assists per game
   - **Shooting Percentages**: FG%, 3P%, FT%
   - **Game-by-Game Stats**: Full breakdown for each game
   - **Assigned Clips**: What they should be watching
   - **Viewing Progress**: What they've watched and acknowledged

### Team Statistics

1. Go to "Teams"
2. Select your team
3. Click "Team Stats"
4. View:
   - All players' season averages
   - Team totals
   - Comparative stats
   - Top performers in each category

### Viewing Clip Engagement

Track which players are watching their assigned clips:

1. Go to "Clips"
2. Select any assigned clip
3. View assignment status:
   - **Not Viewed**: Player hasn't opened the clip yet
   - **Viewed**: Player has watched it (timestamp recorded)
   - **Acknowledged**: Player marked it as reviewed

This helps you:
- Follow up with players who haven't watched
- Know which clips are getting attention
- Measure engagement with film study

### Using Data for Coaching

**In Practice**
- Reference specific clips: "Remember the clip I sent about help defense?"
- Work on areas shown in stats: "Let's improve that FT%, I saw you went 3-for-10 last game"
- Celebrate improvements: "Your assist numbers are up from last month!"

**With Parents**
- Parents can see their child's stats
- They have access to the same clips their child sees
- This creates accountability and engagement at home

**Individual Meetings**
- Pull up a player's dashboard
- Review stats trends together
- Watch clips with the player
- Set specific goals for the next game

## Troubleshooting

### Can't Sign In
- Ensure you're using the correct Google account
- Check that your email is authorized by your administrator
- Try clearing browser cookies and cache

### Video Upload Fails
- Check file size (very large files may timeout)
- Verify video format is supported
- Ensure stable internet connection
- Try a different browser

### Clip Processing Stuck
- Clips usually process in under 30 seconds
- If stuck for over 5 minutes, try refreshing the page
- Contact your administrator if it remains stuck

### Player Can't Access Invite
- Verify the invite code was copied correctly
- Check that the invite hasn't expired (30-day default)
- Ensure the player is using the correct invite link format

### Annotations Not Saving
- Ensure the clip has completed processing first
- Check that you have a stable internet connection
- Try refreshing and annotating again

## Tips for Success

### Organizing Your Workflow

1. **Upload videos immediately after games** while details are fresh
2. **Create clips within 24 hours** for timely feedback
3. **Add annotations and voice-over** before assigning
4. **Assign clips early in the week** so players have time to review
5. **Enter stats promptly** for accurate tracking
6. **Follow up mid-week** on who's watched their clips
7. **Reference clips in practice** for maximum impact

### Making the Most of Film Study

- **Quality over quantity**: 3-5 well-annotated clips are better than 20 without context
- **Balance positive and constructive**: Show what they did well, not just mistakes
- **Be specific**: General comments like "do better" don't help; specific techniques do
- **Connect to practice**: Use clips to illustrate what you're teaching
- **Create playlists**: Group related clips (all defensive clips, all from one player, etc.)

### Engaging Players

- **Make it personal**: Voice-over creates connection
- **Acknowledge their viewing**: Thank players who watch their clips
- **Ask questions**: "What did you notice in that clip I sent?"
- **Show improvement**: Send clips showing how they've gotten better
- **Include them in success**: Send clips of great team plays
