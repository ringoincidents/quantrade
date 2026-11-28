import unittest
from observation_validator import validate

def fixture():
    return [dict(period="2020Q1",unit="REAL_GDP_QOQ_ANNUALIZED_PERCENT",issued_at="2020-02-01T00:00:00Z",actual_public_at="2020-04-30T00:00:00Z",source_sha256="a"*64,vintage="FIRST_RELEASE",actual=1,spf=2,iar=3),dict(period="2020Q2",unit="REAL_GDP_QOQ_ANNUALIZED_PERCENT",issued_at="2020-05-15T00:00:00Z",actual_public_at="2020-07-30T00:00:00Z",source_sha256="b"*64,vintage="FIRST_RELEASE",actual=4,spf=5,iar=6)]

class TestValidator(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate(fixture())["actual"],[1,4])
    def test_reject(self):
        for key,value in [("period","2020Q3"),("unit","YOY"),("issued_at","2020-04-01T00:00:00Z"),("vintage","REVISED"),("source_sha256","bad"),("actual",float("nan")),("issued_at","2020-05-15T00:00:00")]:
            with self.subTest(key=key,value=value):
                rows=fixture(); rows[1][key]=value
                with self.assertRaises(ValueError): validate(rows)
