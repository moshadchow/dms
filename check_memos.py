from sqlalchemy import create_engine, text
from core.config import settings

e = create_engine(settings.DATABASE_URL)
c = e.connect()

t = c.execute(text("select column_name from information_schema.columns where table_name='memos' order by ordinal_position")).fetchall()
print("memos columns:", [x[0] for x in t])

c.close()
print("Done")