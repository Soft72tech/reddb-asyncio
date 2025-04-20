from sqlalchemy import create_engine

def test_create_engine():
    engine = create_engine('firebird+fdb://', echo=True)
    


