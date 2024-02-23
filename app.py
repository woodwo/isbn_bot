#!/usr/bin/env python

import html
import json
import logging
import re
import traceback
import uuid
from io import BytesIO


from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    ConversationHandler,
    PicklePersistence,
    filters,
)

from telegram.constants import ParseMode


from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dataclasses import dataclass
from books.models import Book, Box, Base

from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_

# from telegram_handler import TelegramLoggingHandler
import cv2
from pyzbar.pyzbar import decode
import urllib.request
from transliterate import translit


# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

DEVELOPER_CHAT_ID = 176502779

from functools import wraps

LIST_OF_ADMINS = [176502779, 445937181]


# Function to transliterate Russian text to English
def transliterate_russian_to_english(text):
    return translit(text, "ru", reversed=True)


def restricted_method(func):
    @wraps(func)
    async def wrapped(instance, update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in LIST_OF_ADMINS:
            logger.warn(f"Unauthorized access denied for {user_id}.")
            await update.message.reply_text(
                "Sorry, this bot is not ready for production yet ¯\_(ツ)_/¯."
            )
            return
        return await func(instance, update, context, *args, **kwargs)

    return wrapped


def barcode(image):
    # read the image in numpy array using cv2
    img = cv2.imread(image)

    # Decode the barcode image
    detectedBarcodes = decode(img)

    # If not detected then print the message
    if not detectedBarcodes:
        print("Barcode Not Detected or your barcode is blank/corrupted!")
    else:
        # Traverse through all the detected barcodes in image
        for barcode in detectedBarcodes:
            # Locate the barcode position in image
            (x, y, w, h) = barcode.rect

            # Put the rectangle in image using
            # cv2 to highlight the barcode
            cv2.rectangle(
                img, (x - 10, y - 10), (x + w + 10, y + h + 10), (255, 0, 0), 2
            )

            if barcode.data != "":
                # Print the barcode data
                logger.info("Barcode on %s is: %s", image, barcode.data)
                cv2.imwrite(image, img)
                return barcode.data, image


def isbn_db(isbn):
    base_api_link = "https://www.googleapis.com/books/v1/volumes?q=isbn:"
    url = f"{base_api_link}{isbn}&country=RU"
    request = urllib.request.Request(url, data=None)
    with urllib.request.urlopen(request) as f:
        text = f.read()

    decoded_text = text.decode("utf-8")
    return json.loads(decoded_text)


async def downloader(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Download file
    new_file = await update.message.effective_attachment[-1].get_file()
    file = await new_file.download_to_drive()

    return file


BOX, ADD_BOX, DESCRIPTION, COVER = range(4)


class DatabaseHandler:
    def __init__(self, database_url):
        self.engine = create_engine(database_url)
        Base.metadata.bind = self.engine
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)

    def read_boxes(self):
        boxes = []
        with self.Session() as session:
            boxes = session.query(Box).all()
            session.expunge_all()

        return boxes

    def create_box(self, new_box_name):
        with self.Session() as session:
            new_box = Box(name_of_the_box=new_box_name)
            session.add(new_box)
            session.commit()

    def create_book(self, title, isbn, author, year, description, box):
        new_book = Book(
            title=title,
            isbn=isbn,  # TODO check the same
            author=author,
            year=year,
            description=description,
            box=box,
        )
        with self.Session() as session:
            try:
                session.add(new_book)
                session.commit()

            except IntegrityError:
                logger.error("The book already exists, %s, %s", title, isbn)

        with self.Session() as session:
            # Retrieve the persisted instance with eager loading of 'box'
            persisted_book = (
                session.query(Book)
                .options(joinedload(Book.box))
                .filter_by(isbn=new_book.isbn)
                .first()
            )
            session.expunge_all()

        return persisted_book

    def add_image_to_book(self, book, cover_binary):
        with self.Session() as session:
            book = session.query(Book).filter_by(id=book.id).first()
            if book:
                book.cover = cover_binary
                session.commit()

    def search_books_by_keyword(self, keyword):
        with self.Session() as session:
            # Using ilike for case-insensitive search
            query = (
                session.query(Book)
                .options(joinedload(Book.box))
                .filter(
                    or_(
                        Book.title.ilike(f"%{keyword}%"),
                        Book.author.ilike(f"%{keyword}%"),
                        Book.description.ilike(f"%{keyword}%"),
                    )
                )
                .all()
            )
            return query

    def books_in_box(self, box_name):
        logger.info(f"Find in box named: {box_name}")

        with self.Session() as session:
            box = session.query(Box).filter_by(name_of_the_box=box_name).first()
            if box:
                books = session.query(Book).filter_by(box=box).all()
                return books
            else:
                return []


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # Log the error before we do anything else, so we can see it even if something breaks.
    logger.error("Exception while handling an update:", exc_info=context.error)

    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string, so we have to join them together.
    tb_list = traceback.format_exception(
        None, context.error, context.error.__traceback__
    )
    tb_string = "".join(tb_list)

    # Build the message with some markup and additional information about what happened.
    # You might need to add some logic to deal with messages longer than the 4096 character limit.
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        "An exception was raised while handling an update\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )

    # Finally, send the message
    await context.bot.send_message(
        chat_id=DEVELOPER_CHAT_ID, text=message, parse_mode=ParseMode.HTML
    )


class BookShelfBot:
    box: Box
    new_box_caption = "Add new box"

    def __init__(self, token, db_handler):
        self.token = token
        # TODO here we will read boxes
        self.book = Book
        self.db_handler = db_handler

    def run(self):
        persistence = PicklePersistence(filepath="conversationbot")
        application = (
            Application.builder().token(token).build()
        )  # .persistence(persistence).build()

        # TODO split to box and book?
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", self.start)],
            states={
                BOX: [
                    MessageHandler(
                        filters.Regex("^Box.+$") | filters.Regex("^Add new box$"),
                        self.box,
                    )
                ],
                ADD_BOX: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_box)
                ],
                DESCRIPTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.description),
                    MessageHandler(filters.PHOTO, self.recognize_isbn),
                ],
                COVER: [
                    MessageHandler(filters.PHOTO, self.cover),
                    CommandHandler("skip", self.skip_cover),
                ],
            },
            fallbacks=[
                CommandHandler("cancel", self.cancel),
                CommandHandler("stop", self.cancel),
                CommandHandler("exit", self.cancel),
            ],
            name="conversation",
            # persistent=True,
        )

        application.add_handler(conv_handler)
        application.add_handler(CommandHandler("book", self.find_book))
        application.add_handler(CommandHandler("find", self.find_book))
        application.add_handler(CommandHandler("box", self.books_by_box))

        # ...and the error handler
        application.add_error_handler(error_handler)

        application.run_polling()

    @restricted_method
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Starts the conversation and asks the user about their gender."""
        boxes = self.db_handler.read_boxes()
        logger.info([box.name_of_the_box for box in boxes])

        buttons = [box.name_of_the_box for box in boxes]
        buttons.append(self.new_box_caption)
        logger.info("Box buttons are: %s", buttons)
        reply_keyboard = [buttons]

        # await update.effective_message.reply_html(
        #     "Use /bad_command to cause an error.\n"
        #     f"Your chat id is <code>{update.effective_chat.id}</code>."
        # )

        await update.message.reply_text(
            "Hi! I will hold a conversation with you. "
            "Send /cancel to stop.\n\n"
            "Do you want to add a box or select one?",
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard,
                one_time_keyboard=True,
                input_field_placeholder="Select box here or add a new one",
            ),
        )

        return BOX

    @restricted_method
    async def add_box(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Chose self.box (or add a new one too)."""
        logger.info("Adding box: %s", update.message.text)

        chosen = f"Box {update.message.text}"
        self.db_handler.create_box(chosen)
        boxes = self.db_handler.read_boxes()

        logger.info([box.name_of_the_box for box in boxes])

        filtered_boxes = list(filter(lambda box: box.name_of_the_box == chosen, boxes))
        # TODO: return err here?
        chosen_box = filtered_boxes[0]

        logger.info("Box: %s", chosen_box.name_of_the_box)
        self.box = chosen_box

        await update.message.reply_text(
            f"You selected box: {chosen_box.name_of_the_box}, now put a book to it. What is the book data? Send me title, author, year, description",
            reply_markup=ReplyKeyboardRemove(),
        )

        return DESCRIPTION

    @restricted_method
    async def box(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Chose self.box (or add a new one too)."""
        logger.info("Box option: %s", update.message.text)

        chosen = update.message.text
        if chosen == self.new_box_caption:
            await update.message.reply_text(
                f"What is the name of new box?",
                reply_markup=ReplyKeyboardRemove(),
            )
            return ADD_BOX

        boxes = self.db_handler.read_boxes()

        logger.info([box.name_of_the_box for box in boxes])
        filtered_boxes = list(filter(lambda box: box.name_of_the_box == chosen, boxes))
        # TODO: return err here?
        chosen_box = filtered_boxes[0]

        logger.info("Box: %s", chosen_box.name_of_the_box)
        self.box = chosen_box

        await update.message.reply_text(
            f"You selected box: {chosen_box.name_of_the_box}, now put a book to it. What is the book data? Send me barcode photo or title, author, year, description",
            reply_markup=ReplyKeyboardRemove(),
        )

        return DESCRIPTION

    @restricted_method
    async def description(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Stores the selected description and asks for a photo."""
        logger.info("Description of new book: %s", update.message.text)
        delimiters = [",", ";", "|", "\n"]  # Add more delimiters as needed
        for delimiter in delimiters:
            if delimiter in update.message.text:
                title, author, year, description = update.message.text.split(delimiter)

                # Transliterate if text is in Russian
                if any(
                    cyrillic_char in title + author + year + description
                    for cyrillic_char in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
                ):
                    title = transliterate_russian_to_english(title)
                    author = transliterate_russian_to_english(author)
                    description = transliterate_russian_to_english(description)
                break
        else:
            # Handle case when none of the delimiters are found
            await update.message.reply_text(
                "Sorry, no delimiters in the message, try comma -> ,"
            )
            return DESCRIPTION

        self.book = self.db_handler.create_book(
            title=title,  # unsafe
            isbn=uuid.uuid4().hex,
            author=author,
            year=year,
            description=description,
            box=self.box,
        )

        await update.message.reply_text(
            "Ok! Please send me a photo of cover, "
            "so I know what it look like, or send /skip if you don't want to.",
        )

        return COVER

    @restricted_method
    async def recognize_isbn(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if (
            not update.message
            or not update.effective_chat
            or (
                not update.message.photo
                and not update.message.video
                and not update.message.document
                and not update.message.sticker
                and not update.message.animation
            )
        ):
            return
        file = await downloader(update, context)

        if not file:
            await update.message.reply_text("Something went wrong, try again")
            return

        try:
            isbn, img = barcode(file.as_posix())
        except TypeError:
            await update.message.reply_text(
                f"Oops no barcode found info! Send me a title, author, year, description"
            )
            return DESCRIPTION

        raw = isbn_db(isbn.decode("utf-8"))
        logger.info(raw)

        # await update.message.reply_text(raw)
        # TODO to func process
        if raw["totalItems"] != 1:
            await update.message.reply_text(
                f"Oops no barcode {isbn} info! Send me a title, author, year, description"
            )
            await update.message.reply_photo(img)
            return DESCRIPTION

        item = raw["items"][0]["volumeInfo"]  # unsafe
        self.book = self.db_handler.create_book(
            title=item["title"],  # unsafe
            isbn=isbn,  # TODO check the same
            author=",".join(item.get("authors", list())),
            year=item["publishedDate"],
            description=item.get("description", ""),
            box=self.box,
        )

        # logger.info("Book recognised as: %s", self.book)
        await update.message.reply_text(
            f"Ok! i know this book, {self.book.__str__()}, now send me a cover"
        )

        return COVER

    @restricted_method
    async def cover(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Stores the photo and asks for a location."""
        file = await downloader(update, context)

        logger.info("Photo of cover: %s", file.as_posix())
        self.db_handler.add_image_to_book(self.book, file.read_bytes())

        await update.message.reply_text("Ok, done, now you can add another book")
        await update.message.reply_text(
            "Please send me a photo of cover, so I know what it look like. Or send me a title, author, year, description."
        )

        return DESCRIPTION

    @restricted_method
    async def skip_cover(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        await update.message.reply_text("Ok, now you can add another book")
        await update.message.reply_text(
            "Please send me a photo of cover, so I know what it look like. Or send me a title, author, year, description."
        )

        return DESCRIPTION

    @restricted_method
    async def find_book(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Return a book by isbn or title."""
        logger.info("Description of new book: %s", update.message.text)
        args = context.args

        # Check if any arguments were provided
        if not args:
            await update.message.reply_text("Please provide a keyword to search for")
            return

        for arg in args:
            if any(
                cyrillic_char in arg
                for cyrillic_char in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
            ):
                args.append(transliterate_russian_to_english(arg))

        for arg in args:
            books = self.db_handler.search_books_by_keyword(arg)
            if not books:
                await update.message.reply_text(
                    f"Opps! I did not find anything by {arg}"
                )

            for book in books:
                await update.message.reply_text(f"{book}")
                # Send cover image as photo
                if book.cover:
                    cover_image = BytesIO(book.cover)
                    cover_image.name = (
                        "cover.jpg"  # You can change the filename if needed
                    )
                    await update.message.reply_photo(cover_image)
                else:
                    await update.message.reply_text(
                        f"Opps! No cover image for this book"
                    )

    @restricted_method
    async def books_by_box(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        box_name = self.box.__str__()  # TODO by box itself

        books = self.db_handler.books_in_box(box_name)
        if books:
            book_list = "\n".join([f"{book.title} - {book.author}" for book in books])
            await update.message.reply_text(f"Books in {box_name}:\n{book_list}")
        else:
            await update.message.reply_text(f"No books found in {box_name}")
        return DESCRIPTION

    @restricted_method
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancels and ends the conversation."""
        user = update.message.from_user
        logger.info("User %s canceled the conversation.", user.first_name)
        await update.message.reply_text(
            "Bye! I hope we can talk again some day.",
            reply_markup=ReplyKeyboardRemove(),
        )

        return ConversationHandler.END


if __name__ == "__main__":
    import os
    import sys

    # persistence = PicklePersistence(filepath="tutorhelpbot")

    # Retrieve the token from the environment variable
    token = os.environ.get("TOKEN")

    # Check if the token is available
    if token is None:
        print("Token not found in the environment variable.")
        sys.exit(1)

    bot = BookShelfBot(token, DatabaseHandler("sqlite:///data/books.db"))
    bot.run()
