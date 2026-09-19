from sqlalchemy import create_engine, text
from core.config import settings

e = create_engine(settings.DATABASE_URL)
c = e.connect()

# Check memos table has company_id (e597bede3373)
t = c.execute(text("select column_name from information_schema.columns where table_name='memos' order by ordinal_position")).fetchall()
print("memos columns:", [x[0] for x in t])
has_company_id = any(x[0] == 'company_id' for x in t)
print("memos has company_id:", has_company_id)

c.close()
