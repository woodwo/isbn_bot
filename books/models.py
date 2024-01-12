# books/models.py
from sqlalchemy import Column, Integer, String, ForeignKey, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import UniqueConstraint


Base = declarative_base()

class Box(Base):
    __tablename__ = 'boxes'

    id = Column(Integer, primary_key=True)
    name_of_the_box = Column(String, nullable=False)
    books = relationship('Book', back_populates='box')

    def __str__(self):
        return f"{self.name_of_the_box}"

class Book(Base):
    __tablename__ = 'books'

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    isbn = Column(String, unique=True)  # Add unique constraint to ISBN
    author = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    description = Column(String)
    cover = Column(LargeBinary)
    box_id = Column(Integer, ForeignKey('boxes.id', ondelete='CASCADE'))
    box = relationship('Box', back_populates='books')

    # Add unique constraint to ISBN across the entire table
    __table_args__ = (UniqueConstraint('isbn', name='unique_isbn'),)

    def __str__(self):
        return f"{self.title}, {self.isbn}, {self.author}, {self.box}"
