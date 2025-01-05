import os
import pandas as pd
from dotenv import load_dotenv
import matplotlib.pyplot as plt
from io import BytesIO
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import logging
import re

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Load the Excel file
data_file = "prof_grades.xlsx"  # Replace with your file path
df = pd.read_excel(data_file)
df["Year"] = df["Year"].astype(str)
df["Semester"] = df["Semester"].astype(str)

# Dictionary to store user states
user_states = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    user_states[user_id] = "WAITING_FOR_COURSE"
    await update.message.reply_text("Send me a course code to get data.")



async def handle_course(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id

    if user_states.get(user_id) != "WAITING_FOR_COURSE":
        await update.message.reply_text("Please wait until the current process is completed.")
        return

    user_states[user_id] = "PROCESSING"
    await update.message.reply_text("Searching for the course, please wait...")

    # Extract the base course code (first six characters)
    course_code = update.message.text.strip().upper()[:6]

    # Use a regex to match all courses starting with this base code
    pattern = f"^{re.escape(course_code)}.*$"
    filtered = df[df["Course"].str.match(pattern, na=False)]

    if filtered.empty:
        user_states[user_id] = "WAITING_FOR_COURSE"
        await update.message.reply_text("No data found for this course. Please try another course code. /start")
        return

    years = filtered["Year"].unique()
    keyboard = [[InlineKeyboardButton(year, callback_data=f"{course_code}|{year}")] for year in years]

    reply_markup = InlineKeyboardMarkup(keyboard)
    user_states[user_id] = "WAITING_FOR_YEAR"
    await update.message.reply_text("Select a year:", reply_markup=reply_markup)




async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data.split("|")
    
    await query.answer()

    # Handle Year Selection
    if len(data) == 2 and user_states.get(user_id) == "WAITING_FOR_YEAR":
        course_code, year = data
        # Use regex to match the base course code
        pattern = f"^{re.escape(course_code)}.*$"
        filtered = df[(df["Course"].str.match(pattern, na=False)) & (df["Year"] == year)]

        if filtered.empty:
            user_states[user_id] = "WAITING_FOR_COURSE"
            await query.message.reply_text("No data found. Please try again. /start")
            return

        semesters = filtered["Semester"].unique()
        keyboard = [[InlineKeyboardButton(semester, callback_data=f"{course_code}|{year}|{semester}")] for semester in semesters]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        user_states[user_id] = "WAITING_FOR_SEMESTER"
        await query.message.reply_text("Select a semester:", reply_markup=reply_markup)

    # Handle Semester Selection
    elif len(data) == 3 and user_states.get(user_id) == "WAITING_FOR_SEMESTER":
        course_code, year, semester = data
        # Use regex to match the base course code
        pattern = f"^{re.escape(course_code)}.*$"
        filtered = df[(df["Course"].str.match(pattern, na=False)) & 
                      (df["Year"] == year) & 
                      (df["Semester"] == semester)]

        labels = filtered["Grade"]
        sizes = filtered["Count"]

        if sizes.empty:
            user_states[user_id] = "WAITING_FOR_COURSE"
            await query.message.reply_text("No data found. Please try again. /start")
            return

        # Generate Pie Chart and Table
        fig, ax = plt.subplots(1, 2, figsize=(12, 6), facecolor="black")
        ax[0].pie(sizes, labels=labels, autopct="%1.1f%%", startangle=140, textprops={"color": "white"})
        ax[0].set_title(f"Grades Distribution\n{course_code}", color="white", fontsize=14)

        ax[1].axis("tight")
        ax[1].axis("off")
        table_data = [[grade, count] for grade, count in zip(filtered["Grade"], filtered["Count"])]
        table = ax[1].table(cellText=table_data, colLabels=["Grade", "Count"], loc="center", cellLoc="center")
        table.auto_set_font_size(False)
        table.set_fontsize(12)
        table.scale(1, 1.5)
        ax[1].set_title(f"Year: {year}\nSemester: {semester}", color="white", fontsize=12)

        buffer = BytesIO()
        plt.savefig(buffer, format="png", facecolor=fig.get_facecolor())
        buffer.seek(0)
        plt.close()

        user_states[user_id] = "WAITING_FOR_COURSE"
        await query.message.reply_photo(photo=buffer)
        buffer.close()

        await query.message.reply_text("To get started click here /start")

    else:
        await query.message.reply_text("Invalid selection. Please start again using /start.")
        user_states[user_id] = "WAITING_FOR_COURSE"





def main():
    # Retrieve the bot token
    load_dotenv()
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("Bot token is missing. Set TELEGRAM_BOT_TOKEN environment variable.")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_course))
    application.add_handler(CallbackQueryHandler(callback_handler))


    application.run_polling()

if __name__ == "__main__":
    main()
