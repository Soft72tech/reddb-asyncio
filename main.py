from sqlalchemy import create_engine

def main():
    engine = create_engine('firebird://', echo=True)


def test_connection():
    pass


if __name__ == "__main__":
    main()
