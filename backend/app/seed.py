from __future__ import annotations

from sqlalchemy.orm import Session

from .models import Problem, TestCase

SEED_CATEGORIES = {
    "Сумма двух чисел": "математика",
    "Максимум из трёх чисел": "математика",
    "Сумма последовательности": "математика",
    "Палиндром": "строки",
    "Факториал": "математика",
    "Простое число": "математика",
    "Число Фибоначчи": "математика",
    "Максимальная сумма отрезка": "динамическое программирование",
    "Кратчайший путь в графе": "графы",
}


def seed_if_empty(db: Session) -> None:
    if db.query(Problem).first() is not None:
        return
    for item in PROBLEMS:
        problem = Problem(
            title=item["title"],
            short_description=item["short_description"],
            statement=item["statement"],
            input_format=item["input_format"],
            output_format=item["output_format"],
            constraints=item["constraints"],
            difficulty=item["difficulty"],
            category=SEED_CATEGORIES.get(item["title"], "общее"),
            time_limit_ms=item["time_limit_ms"],
            memory_limit_mb=256,
        )
        db.add(problem)
        db.flush()
        for index, test in enumerate(item["tests"]):
            db.add(
                TestCase(
                    problem_id=problem.id,
                    input_data=test[0],
                    expected_output=test[1],
                    is_sample=test[2],
                    order_index=index,
                )
            )
    db.commit()


def ensure_seed_categories(db: Session) -> None:
    changed = False
    for problem in db.query(Problem).all():
        category = SEED_CATEGORIES.get(problem.title)
        if category and problem.category == "общее":
            problem.category = category
            changed = True
    if changed:
        db.commit()


PROBLEMS = [
    {
        "title": "Сумма двух чисел",
        "short_description": "Сложите два целых числа.",
        "statement": "Даны два целых числа a и b. Выведите их сумму.",
        "input_format": "Одна строка содержит два целых числа a и b, разделённые пробелом.",
        "output_format": "Одно целое число — сумма a и b.",
        "constraints": "−10^9 ≤ a, b ≤ 10^9",
        "difficulty": "easy",
        "time_limit_ms": 1000,
        "tests": [
            ("2 3", "5", True),
            ("-1 1", "0", True),
            ("1000000000 1000000000", "2000000000", False),
            ("0 0", "0", False),
        ],
    },
    {
        "title": "Максимум из трёх чисел",
        "short_description": "Найдите наибольшее из трёх целых чисел.",
        "statement": "Даны три целых числа. Выведите наибольшее из них.",
        "input_format": "Одна строка содержит три целых числа, разделённые пробелами.",
        "output_format": "Одно целое число — максимум из трёх.",
        "constraints": "−10^9 ≤ каждое число ≤ 10^9",
        "difficulty": "easy",
        "time_limit_ms": 1000,
        "tests": [
            ("3 1 2", "3", True),
            ("-5 -1 -8", "-1", True),
            ("7 7 7", "7", False),
            ("0 -2 5", "5", False),
        ],
    },
    {
        "title": "Сумма последовательности",
        "short_description": "Посчитайте сумму n целых чисел.",
        "statement": "В первой строке дано целое число n — количество элементов. Во второй строке даны n целых чисел. Выведите их сумму.",
        "input_format": "Первая строка содержит n. Вторая строка содержит n целых чисел.",
        "output_format": "Одно целое число — сумма элементов.",
        "constraints": "1 ≤ n ≤ 1000, |ai| ≤ 10^6",
        "difficulty": "easy",
        "time_limit_ms": 1000,
        "tests": [
            ("5\n1 2 3 4 5", "15", True),
            ("1\n42", "42", True),
            ("3\n-1 0 1", "0", False),
            ("4\n10 20 30 40", "100", False),
        ],
    },
    {
        "title": "Палиндром",
        "short_description": "Проверьте, читается ли строка одинаково в обе стороны.",
        "statement": "Дана непустая строка без пробелов. Выведите YES, если она палиндром, и NO иначе. Сравнение чувствительно к регистру.",
        "input_format": "Одна строка s.",
        "output_format": "YES или NO.",
        "constraints": "1 ≤ |s| ≤ 1000, строка не содержит пробелов.",
        "difficulty": "easy",
        "time_limit_ms": 1000,
        "tests": [
            ("aba", "YES", True),
            ("abc", "NO", True),
            ("a", "YES", False),
            ("abba", "YES", False),
            ("AbA", "YES", False),
            ("казак", "YES", False),
        ],
    },
    {
        "title": "Факториал",
        "short_description": "Вычислите факториал числа n.",
        "statement": "Дано целое число n. Вычислите n!. Считайте, что 0! = 1.",
        "input_format": "Одно целое число n.",
        "output_format": "Значение n!.",
        "constraints": "0 ≤ n ≤ 15",
        "difficulty": "medium",
        "time_limit_ms": 2000,
        "tests": [
            ("0", "1", True),
            ("5", "120", True),
            ("1", "1", False),
            ("10", "3628800", False),
            ("15", "1307674368000", False),
        ],
    },
    {
        "title": "Простое число",
        "short_description": "Проверьте, является ли число простым.",
        "statement": "Дано целое число n. Выведите YES, если n простое, и NO иначе. Простым называется натуральное число больше 1, которое не делится ни на одно число кроме 1 и самого себя.",
        "input_format": "Одно целое число n.",
        "output_format": "YES или NO.",
        "constraints": "1 ≤ n ≤ 10^6",
        "difficulty": "medium",
        "time_limit_ms": 2000,
        "tests": [
            ("2", "YES", True),
            ("1", "NO", True),
            ("18", "NO", False),
            ("17", "YES", False),
            ("97", "YES", False),
            ("100", "NO", False),
            ("7919", "YES", False),
        ],
    },
    {
        "title": "Число Фибоначчи",
        "short_description": "Найдите n-е число Фибоначчи.",
        "statement": "Числа Фибоначчи задаются так: F(0) = 0, F(1) = 1, F(i) = F(i − 1) + F(i − 2) для i ≥ 2. По данному n выведите F(n).",
        "input_format": "Одно целое число n.",
        "output_format": "Значение F(n).",
        "constraints": "0 ≤ n ≤ 30",
        "difficulty": "medium",
        "time_limit_ms": 2000,
        "tests": [
            ("0", "0", True),
            ("10", "55", True),
            ("1", "1", False),
            ("2", "1", False),
            ("20", "6765", False),
            ("30", "832040", False),
        ],
    },
    {
        "title": "Максимальная сумма отрезка",
        "short_description": "Найдите непрерывный подотрезок с наибольшей суммой.",
        "statement": "В первой строке дано n. Во второй строке заданы n целых чисел. Найдите непрерывный подотрезок с максимальной суммой. Подотрезок должен содержать хотя бы один элемент.",
        "input_format": "Первая строка содержит n. Вторая строка содержит n целых чисел.",
        "output_format": "Максимальная сумма непрерывного подотрезка.",
        "constraints": "1 ≤ n ≤ 1000, |ai| ≤ 10^6",
        "difficulty": "hard",
        "time_limit_ms": 2000,
        "tests": [
            ("8\n-2 1 -3 4 -1 2 1 -5 4", "6", True),
            ("1\n5", "5", True),
            ("4\n-5 -1 -3 -2", "-1", False),
            ("5\n5 4 -10 7 8", "15", False),
            ("3\n-2 1 -3", "1", False),
        ],
    },
    {
        "title": "Кратчайший путь в графе",
        "short_description": "Найдите расстояние между двумя вершинами невзвешенного графа.",
        "statement": "Дан неориентированный граф без петель и кратных рёбер. В первой строке даны n и m — число вершин и рёбер. Следующие m строк содержат рёбра u v. В последней строке даны вершины s и t. Выведите длину кратчайшего пути от s до t в числе рёбер. Если пути нет, выведите -1. Вершины пронумерованы с 1.",
        "input_format": "Первая строка: n m. Далее m строк с рёбрами. Последняя строка: s t.",
        "output_format": "Длина кратчайшего пути или -1.",
        "constraints": "1 ≤ n ≤ 1000, 0 ≤ m ≤ 5000, 1 ≤ s, t ≤ n",
        "difficulty": "hard",
        "time_limit_ms": 2000,
        "tests": [
            ("4 3\n1 2\n2 3\n3 4\n1 4", "3", True),
            ("3 1\n1 2\n1 3", "-1", True),
            ("2 0\n1 1", "0", False),
            ("5 4\n1 2\n2 3\n3 5\n4 5\n1 5", "3", False),
            ("4 4\n1 2\n2 3\n3 4\n1 3\n1 4", "2", False),
            ("6 4\n1 2\n2 3\n4 5\n5 6\n1 6", "-1", False),
        ],
    },
]
