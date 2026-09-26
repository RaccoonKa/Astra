import re
from datetime import datetime, timedelta

NUM_WORDS = {
    "ноль": 0, "одну": 1, "один": 1, "одна": 1, "две": 2, "два": 2, "три": 3,
    "четыре": 4, "пять": 5, "шесть": 6, "семь": 7, "восемь": 8, "девять": 9,
    "десять": 10, "одиннадцать": 11, "двенадцать": 12, "тринадцать": 13,
    "четырнадцать": 14, "пятнадцать": 15, "шестнадцать": 16, "семнадцать": 17,
    "восемнадцать": 18, "девятнадцать": 19, "двадцать": 20, "тридцать": 30,
    "сорок": 40, "пятьдесят": 50, "полтора": 1.5, "полторы": 1.5
}

MONTHS = {
    "января": 1, "январь": 1,
    "февраля": 2, "февраль": 2,
    "марта": 3, "март": 3,
    "апреля": 4, "апрель": 4,
    "мая": 5, "май": 5,
    "июня": 6, "июнь": 6,
    "июля": 7, "июль": 7,
    "августа": 8, "август": 8,
    "сентября": 9, "сентябрь": 9,
    "октября": 10, "октябрь": 10,
    "ноября": 11, "ноябрь": 11,
    "декабря": 12, "декабрь": 12
}

WEEKDAYS = {
    "понедельник": 0, "пн": 0,
    "вторник": 1, "вт": 1,
    "среду": 2, "среда": 2, "ср": 2,
    "четверг": 3, "чт": 3,
    "пятницу": 4, "пятница": 4, "пт": 4,
    "субботу": 5, "суббота": 5, "сб": 5,
    "воскресенье": 6, "вс": 6
}


class TimeParser:
    @classmethod
    def _words_to_number(cls, text: str) -> float | None:
        text = text.strip().lower()
        if not text:
            return None

        if text in ["полчаса", "пол-часа"]:
            return 30.0

        try:
            return float(text.replace(",", "."))
        except ValueError:
            pass

        tokens = text.split()
        total = 0.0
        found = False

        for t in tokens:
            if t in NUM_WORDS:
                total += NUM_WORDS[t]
                found = True
            elif t.isdigit():
                total += float(t)
                found = True

        return total if found else None

    @staticmethod
    def format_duration(seconds: int) -> str:
        h = seconds // 3600
        rem = seconds % 3600
        m = rem // 60
        s = rem % 60

        def _plural(n, form1, form2, form5):
            n_abs = abs(int(n)) % 100
            n_rem = n_abs % 10
            if 10 < n_abs < 20:
                return f"{n} {form5}"
            if n_rem == 1:
                return f"{n} {form1}"
            if 1 < n_rem < 5:
                return f"{n} {form2}"
            return f"{n} {form5}"

        parts = []
        if h > 0:
            parts.append(_plural(h, "час", "часа", "часов"))
        if m > 0:
            parts.append(_plural(m, "минуту", "минуты", "минут"))
        if s > 0:
            parts.append(_plural(s, "секунду", "секунды", "секунд"))

        return " ".join(parts) if parts else "0 секунд"

    @classmethod
    def _parse_date(cls, text_low: str, now: datetime) -> tuple[datetime | None, str]:
        if "послезавтра" in text_low:
            m = re.search(r'\b(?:на|в|во)?\s*послезавтра\b', text_low)
            return now.date() + timedelta(days=2), m.group(0).strip()

        if "завтра" in text_low:
            m = re.search(r'\b(?:на|в|во)?\s*завтра\b', text_low)
            return now.date() + timedelta(days=1), m.group(0).strip()

        if "сегодня" in text_low:
            m = re.search(r'\b(?:на|в|во)?\s*сегодня\b', text_low)
            return now.date(), m.group(0).strip()

        for day_name, w_idx in WEEKDAYS.items():
            pattern = rf'\b(?:на|в|во)?\s*{day_name}\b'
            m = re.search(pattern, text_low)
            if m:
                days_ahead = w_idx - now.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                return now.date() + timedelta(days=days_ahead), m.group(0).strip()

        inv_pattern = (
            rf'\b(?:на|в|во)?\s*(\d{{4}})\s*(?:год[а-у]?|г\.?)?,?\s*'
            rf'(?:на|в|во)?\s*(\d{{1,2}})\s+(' + '|'.join(MONTHS.keys()) + r')\b'
        )
        m_inv = re.search(inv_pattern, text_low)
        if m_inv:
            year = int(m_inv.group(1))
            day_num = int(m_inv.group(2))
            m_name = m_inv.group(3)
            month_num = MONTHS[m_name]
            try:
                cand = datetime(year, month_num, day_num).date()
                return cand, m_inv.group(0).strip()
            except ValueError:
                pass

        std_pattern = (
            rf'\b(?:на|в|во)?\s*(\d{{1,2}})\s+(' + '|'.join(MONTHS.keys()) + r')'
            rf'(?:,?\s*(?:на|в|во)?\s*(\d{{4}})\s*(?:год[а-у]?|г\.?)?)?\b'
        )
        m_std = re.search(std_pattern, text_low)
        if m_std:
            day_num = int(m_std.group(1))
            m_name = m_std.group(2)
            month_num = MONTHS[m_name]
            year_str = m_std.group(3)
            explicit_year = bool(year_str)
            year = int(year_str) if explicit_year else now.year
            try:
                cand = datetime(year, month_num, day_num).date()
                if not explicit_year and cand < now.date():
                    cand = datetime(year + 1, month_num, day_num).date()
                return cand, m_std.group(0).strip()
            except ValueError:
                pass

        dot_pattern = r'\b(?:на|в|во)?\s*(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?(?:\s*(?:год[а-у]?|г\.?))?\b'
        m_dot = re.search(dot_pattern, text_low)
        if m_dot:
            day_num = int(m_dot.group(1))
            month_num = int(m_dot.group(2))
            year_str = m_dot.group(3)
            explicit_year = bool(year_str)
            year = int(year_str) if explicit_year else now.year
            if 1 <= month_num <= 12 and 1 <= day_num <= 31:
                try:
                    cand = datetime(year, month_num, day_num).date()
                    if not explicit_year and cand < now.date():
                        cand = datetime(year + 1, month_num, day_num).date()
                    return cand, m_dot.group(0).strip()
                except ValueError:
                    pass

        year_pattern = r'\b(?:на|в|во)?\s*(\d{4})\s*(?:год[а-у]?|г\.?)\b'
        m_year = re.search(year_pattern, text_low)
        if m_year:
            year = int(m_year.group(1))
            cand = datetime(year, 1, 1).date()
            return cand, m_year.group(0).strip()

        return None, ""

    @classmethod
    def _calc_target_time(cls, now: datetime, base_date, hour: int, minute: int, period: str | None, is_alarm: bool = False) -> datetime:
        if period:
            p = period.lower().strip()
            if p in ["вечера"]:
                if hour < 12:
                    hour += 12
            elif p in ["дня"]:
                if 1 <= hour < 12:
                    hour += 12
            elif p in ["ночи"]:
                if hour == 12:
                    hour = 0
            elif p in ["утра"]:
                if hour == 12:
                    hour = 0
        else:
            if base_date is None or base_date == now.date():
                target_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                diff_sec = (now - target_today).total_seconds()

                if 0 <= diff_sec <= 90:
                    return now + timedelta(seconds=2)

                if target_today <= now:
                    if not is_alarm and hour < 12:
                        alt_hour = hour + 12
                        target_alt = now.replace(hour=alt_hour, minute=minute, second=0, microsecond=0)
                        if target_alt > now:
                            hour = alt_hour

        target_date = base_date if base_date is not None else now.date()
        target = datetime(target_date.year, target_date.month, target_date.day, hour, minute, 0, 0)

        if base_date is None and target <= now:
            target += timedelta(days=1)

        return target

    @classmethod
    def parse_relative_seconds(cls, text: str) -> tuple[int | None, str]:
        text_low = text.lower().strip()

        if "полчаса" in text_low or "пол-часа" in text_low:
            match = re.search(r'(?:через|на|спустя)?\s*пол-?часа', text_low)
            m_str = match.group(0) if match else "полчаса"
            return 1800, m_str

        total_seconds = 0
        matched_pieces = []

        units = [
            (r'(?:через|на|спустя)?\s*(\d+(?:[.,]\d+)?|[а-яё\s]+?)\s*(?:ч|час(?:а|ов)?)\b', 3600),
            (r'(?:через|на|спустя)?\s*(\d+(?:[.,]\d+)?|[а-яё\s]+?)\s*(?:мин(?:ут[а-я]*)?|м)\b', 60),
            (r'(?:через|на|спустя)?\s*(\d+(?:[.,]\d+)?|[а-яё\s]+?)\s*(?:сек(?:унд[а-я]*)?|с)\b', 1)
        ]

        for pattern, mult in units:
            m = re.search(pattern, text_low)
            if m:
                matched_str = m.group(0).strip()
                if re.match(r'^(?:в|во)\s+', matched_str):
                    continue
                val_str = m.group(1).strip()
                val_str = re.sub(r'^(?:через|на|еще|ещё|спустя)\s+', '', val_str).strip()
                num = cls._words_to_number(val_str)
                if num is not None and num > 0:
                    total_seconds += int(num * mult)
                    matched_pieces.append(matched_str)

        if total_seconds > 0:
            return total_seconds, " ".join(matched_pieces)

        return None, ""

    @classmethod
    def parse_absolute_time(cls, text: str, is_alarm: bool = False) -> tuple[datetime | None, str]:
        text_low = text.lower().strip()
        now = datetime.now()

        parsed_date, date_match_str = cls._parse_date(text_low, now)
        text_without_date = text_low.replace(date_match_str, " ") if date_match_str else text_low

        time_match = re.search(
            r'\b(?:(?:в|во|на)\s+)?(\d{1,2})\s*[:.;\-,]\s*(\d{1,2})\b(?:\s*(утра|вечера|дня|ночи))?',
            text_without_date
        )
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
            period = time_match.group(3)
            if 0 <= hour < 24 and 0 <= minute < 60:
                target = cls._calc_target_time(now, parsed_date, hour, minute, period, is_alarm=is_alarm)
                full_match = f"{date_match_str} | {time_match.group(0)}".strip(" |")
                return target, full_match

        space_match = re.search(
            r'\b(?:в|во|на)\s+(\d{1,2})\s+(\d{2})\b(?:\s*(утра|вечера|дня|ночи))?',
            text_without_date
        )
        if space_match:
            hour = int(space_match.group(1))
            minute = int(space_match.group(2))
            period = space_match.group(3)
            if 0 <= hour < 24 and 0 <= minute < 60:
                target = cls._calc_target_time(now, parsed_date, hour, minute, period, is_alarm=is_alarm)
                full_match = f"{date_match_str} | {space_match.group(0)}".strip(" |")
                return target, full_match

        comb_match = re.search(
            r'\b(?:в|во|на)\s+([а-яё\d]+)\s*(?:ч|час[а-я]*)?\s*(\d{1,2}|[а-яё]+(?:\s+[а-яё]+)?)\s*(?:мин[а-я]*)?(?:\s+(утра|вечера|дня|ночи))?\b',
            text_without_date
        )
        if comb_match:
            h_str = comb_match.group(1).strip()
            m_str = comb_match.group(2).strip()
            period = comb_match.group(3)

            h_val = cls._words_to_number(h_str)
            m_val = cls._words_to_number(m_str)

            if h_val is not None and m_val is not None:
                hour = int(h_val)
                minute = int(m_val)
                if 0 <= hour < 24 and 0 <= minute < 60:
                    target = cls._calc_target_time(now, parsed_date, hour, minute, period, is_alarm=is_alarm)
                    full_match = f"{date_match_str} | {comb_match.group(0)}".strip(" |")
                    return target, full_match

        hour_match = re.search(
            r'\b(?:в|во|на)\s+([а-яё\d]+)(?:\s*(?:ч|час[а-я]*))?(?:\s+(утра|вечера|дня|ночи))?\b',
            text_without_date
        )
        if hour_match:
            h_str = hour_match.group(1).strip()
            period = hour_match.group(2)
            h_val = cls._words_to_number(h_str)
            if h_val is not None:
                hour = int(h_val)
                if 0 <= hour < 24:
                    target = cls._calc_target_time(now, parsed_date, hour, 0, period, is_alarm=is_alarm)
                    full_match = f"{date_match_str} | {hour_match.group(0)}".strip(" |")
                    return target, full_match

        if parsed_date is not None:
            target = datetime(parsed_date.year, parsed_date.month, parsed_date.day, 10, 0, 0, 0)
            return target, date_match_str

        return None, ""

    @staticmethod
    def _clean_reminder_text(text: str) -> str:
        cleaned = text.strip()
        cleaned = re.sub(
            r'\b(?:поставь|создай|сделай|установи|добавь|заведи|включи)?\s*(?:мне\s+)?(?:напоминание|напомни(?:ть)?|напомни-ка)\b',
            '',
            cleaned,
            flags=re.IGNORECASE
        ).strip()
        cleaned = re.sub(r'^(?:что|чтобы|о том[,]?\s*что|мне|про|о|об)\s+', '', cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r'[\s;,:.\-]+$', '', cleaned).strip()
        cleaned = re.sub(r'^[\s;,:.\-]+', '', cleaned).strip()
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned

    @classmethod
    def parse_reminder(cls, text: str) -> tuple[datetime | None, str]:
        text_clean = text.strip()

        is_rel_keyword = bool(re.search(r'\b(?:через|спустя)\b', text_clean, flags=re.IGNORECASE))

        if is_rel_keyword:
            rel_sec, match_str = cls.parse_relative_seconds(text_clean)
            if rel_sec:
                target_dt = datetime.now() + timedelta(seconds=rel_sec)
                clean_reminder = text_clean.replace(match_str, " ")
                clean_reminder = cls._clean_reminder_text(clean_reminder)
                return target_dt, clean_reminder or "без описания"

        abs_dt, match_str = cls.parse_absolute_time(text_clean, is_alarm=False)
        if abs_dt:
            clean_reminder = text_clean
            for piece in match_str.split('|'):
                p = piece.strip()
                if p:
                    clean_reminder = re.sub(re.escape(p), ' ', clean_reminder, flags=re.IGNORECASE)
            clean_reminder = cls._clean_reminder_text(clean_reminder)
            return abs_dt, clean_reminder or "без описания"

        if not is_rel_keyword:
            rel_sec, match_str = cls.parse_relative_seconds(text_clean)
            if rel_sec:
                target_dt = datetime.now() + timedelta(seconds=rel_sec)
                clean_reminder = text_clean.replace(match_str, " ")
                clean_reminder = cls._clean_reminder_text(clean_reminder)
                return target_dt, clean_reminder or "без описания"

        return None, ""