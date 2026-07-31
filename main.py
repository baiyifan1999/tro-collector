from collectors.cleaner import clean_defendants
from collectors.courtlistener import collect_all
from models.database import init_db, save_cases


def main():
    results = collect_all()

    if results:
        print(results[0])
    else:
        print("No results collected.")

    init_db()
    save_cases(results)
    clean_defendants()


if __name__ == "__main__":
    main()
