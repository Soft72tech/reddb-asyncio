import logging
from datetime import datetime
from typing import Callable

from rich.console import ConsoleRenderable
from rich.logging import RichHandler
from rich.text import Text


def highlight(style: str) -> dict[str, Callable[[Text], Text]]:
    def highlighter(text: Text) -> Text:
        return Text(text.plain, style=style)

    return {"highlighter": highlighter}


class CustomRichHandler(RichHandler):
    def render_message(
        self, record: logging.LogRecord, message: str
    ) -> ConsoleRenderable:
        time_format = None if self.formatter is None else self.formatter.datefmt
        time_format = time_format or self._log_render.time_format
        log_time = datetime.fromtimestamp(
            record.created
        )  # .astimezone(tzlocal.get_localzone())

        if callable(time_format):
            log_time_display = time_format(log_time)
        else:
            log_time_display = Text(log_time.strftime(time_format))

        if not (
            log_time_display == self._log_render._last_time
            and self._log_render.omit_repeated_times
        ):
            # self.console.print(log_time_display, style="log.time")
            self._log_render._last_time = log_time_display

        extra: dict = getattr(record, "extra", {})

        if "rich" in extra:
            return extra["rich"]

        if "style" in extra:
            record.__dict__.update(highlight(extra["style"]))

        elif "highlighter" in extra:
            setattr(record, "highlighter", extra["highlighter"])

        if "alt" in extra:
            message = extra["alt"]
            setattr(record, "markup", True)

        if "markup" in extra:
            setattr(record, "markup", extra["markup"])

        if "text" in extra:
            setattr(record, "highlighter", lambda _: extra["text"])

        if "omit_repeated_times" in extra:
            setattr(record, "omit_repeated_times", extra["omit_repeated_times"])

        else:
            setattr(record, "omit_repeated_times", False)

        return super().render_message(record, message)
