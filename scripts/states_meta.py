STATES = [('AL','Alabama','01'),('AK','Alaska','02'),('AZ','Arizona','04'),('AR','Arkansas','05'),('CA','California','06'),('CO','Colorado','08'),('CT','Connecticut','09'),('DE','Delaware','10'),('FL','Florida','12'),('GA','Georgia','13'),('HI','Hawaii','15'),('ID','Idaho','16'),('IL','Illinois','17'),('IN','Indiana','18'),('IA','Iowa','19'),('KS','Kansas','20'),('KY','Kentucky','21'),('LA','Louisiana','22'),('ME','Maine','23'),('MD','Maryland','24'),('MA','Massachusetts','25'),('MI','Michigan','26'),('MN','Minnesota','27'),('MS','Mississippi','28'),('MO','Missouri','29'),('MT','Montana','30'),('NE','Nebraska','31'),('NV','Nevada','32'),('NH','New Hampshire','33'),('NJ','New Jersey','34'),('NM','New Mexico','35'),('NY','New York','36'),('NC','North Carolina','37'),('ND','North Dakota','38'),('OH','Ohio','39'),('OK','Oklahoma','40'),('OR','Oregon','41'),('PA','Pennsylvania','42'),('RI','Rhode Island','44'),('SC','South Carolina','45'),('SD','South Dakota','46'),('TN','Tennessee','47'),('TX','Texas','48'),('UT','Utah','49'),('VT','Vermont','50'),('VA','Virginia','51'),('WA','Washington','53'),('WV','West Virginia','54'),('WI','Wisconsin','55'),('WY','Wyoming','56')]
import re
ORD = {"first": "1st", "second": "2nd", "third": "3rd", "fourth": "4th", "fifth": "5th", "sixth": "6th", "seventh": "7th", "eighth": "8th", "ninth": "9th", "tenth": "10th", "eleventh": "11th", "twelfth": "12th", "thirteenth": "13th", "fourteenth": "14th", "fifteenth": "15th", "sixteenth": "16th", "seventeenth": "17th", "eighteenth": "18th", "nineteenth": "19th", "twentieth": "20th"}
def dkey(s):
    """normalize a legislative district label so Open States and Census names compare equal"""
    s = (s or '').lower().replace('state senate district', '').replace('state house district', '').replace('district', '')
    s = re.sub(r'\b0+(\d)', r'\1', s)
    for w, n in ORD.items(): s = re.sub(r'\b' + w + r'\b', n, s)
    s = re.sub(r'\band\b', '', s)
    return re.sub(r'[^a-z0-9]', '', s)
