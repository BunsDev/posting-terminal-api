from dataclasses import dataclass
from typing import Any, Iterable, Self
from rich.text import Text
from textual import on
from textual.binding import Binding
from textual.coordinate import Coordinate
from textual.message import Message
from textual.message_pump import MessagePump
from textual.widgets import DataTable
from textual.widgets.data_table import CellDoesNotExist, CellKey, RowKey, ColumnKey


class PostingDataTable(DataTable[str | Text]):
    DEFAULT_CSS = """\
PostingDataTable {
    &.empty {
        display: none;
    }
}
"""

    BINDINGS = [
        Binding("up,k", "cursor_up", "Cursor Up", show=False),
        Binding("down,j", "cursor_down", "Cursor Down", show=False),
        Binding("right,l", "cursor_right", "Cursor Right", show=False),
        Binding("left,h", "cursor_left", "Cursor Left", show=False),
        Binding("f", "toggle_fixed_columns", "Toggle Fixed Column", show=False),
        Binding("home", "scroll_home", "Home", show=False),
        Binding("end", "scroll_end", "End", show=False),
        Binding("g,ctrl+home", "scroll_top", "Top", show=False),
        Binding("G,ctrl+end", "scroll_bottom", "Bottom", show=False),
    ]

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.cursor_vertical_escape = True
        self.row_disable = False
        self._fixed_columns_bak = None

    @dataclass
    class Checkbox:
        """A checkbox, added to rows to make them enable/disable."""

        checked: bool = False

        def __str__(self) -> str:
            return "■" if self.checked else ""

        def __rich__(self) -> str:
            return "[b]■[/]" if self.checked else ""

        def toggle(self) -> bool:
            """Toggle the checkbox."""
            self.checked = not self.checked
            return self.checked

    @dataclass
    class RowsRemoved(Message):
        data_table: "PostingDataTable"
        explicit_by_user: bool = True

        @property
        def control(self) -> "PostingDataTable":
            return self.data_table

    @dataclass
    class RowsAdded(Message):
        data_table: "PostingDataTable"
        explicit_by_user: bool = True

        @property
        def control(self) -> "PostingDataTable":
            return self.data_table

    def add_row(
        self,
        *cells: str | Text,
        height: int | None = 1,
        key: str | None = None,
        label: str | Text | None = None,
        explicit_by_user: bool = True,
        sender: MessagePump | None = None,
    ) -> RowKey:
        if self.row_disable:
            cells = (self.Checkbox(True),) + cells
        msg = self.RowsAdded(self, explicit_by_user=explicit_by_user)
        if sender:
            msg.set_sender(sender)
        self.post_message(msg)
        return super().add_row(*cells, height=height, key=key, label=label)

    def add_column(
        self,
        label: str | Text | None,
        *,
        width: int | None = None,
        key: str | None = None,
        default: str | Text | None = None,
    ) -> ColumnKey:
        if self.row_disable and len(self.columns) == 0:
            super().add_column("", width=1, key="checkbox")

        return super().add_column(label, width=width, key=key, default=default)

    def action_toggle_fixed_columns(self) -> None:
        if self._fixed_columns_bak is None:
            self._fixed_columns_bak = self.fixed_columns
        self.fixed_columns = self._fixed_columns_bak if self.fixed_columns == 0 else 0

    def remove_row(self, row_key: RowKey | str) -> None:
        self.post_message(self.RowsRemoved(self))
        rv = super().remove_row(row_key)
        self._column_width_refresh()
        return rv

    def clear(self, columns: bool = False) -> Self:
        self.post_message(self.RowsRemoved(self, explicit_by_user=False))
        super().clear(columns=columns)
        self._column_width_refresh()
        return self

    def replace_all_rows(self, rows: Iterable[Iterable[str]]) -> None:
        self.clear()
        for row in rows:
            self.add_row(*row, explicit_by_user=False)
        self._column_width_refresh()

    def _column_width_refresh(self) -> None:
        # TODO - fix this inside Textual.
        if self.row_count > 0:
            row_zero = list(self._data.keys())[0]
            columns = set(list(self._data.values())[0].keys())
            self._update_column_widths(
                {CellKey(row_zero, column) for column in columns}
            )

    def action_cursor_down(self) -> None:
        self._set_hover_cursor(False)
        if (
            self.cursor_coordinate.row == self.row_count - 1
            and self.cursor_vertical_escape
        ):
            self.screen.focus_next()
        else:
            cursor_type = self.cursor_type
            if self.show_cursor and (cursor_type == "cell" or cursor_type == "row"):
                row, column = self.cursor_coordinate
                if row == self.row_count - 1:
                    self.cursor_coordinate = Coordinate(0, column)
                else:
                    self.cursor_coordinate = self.cursor_coordinate.down()
            else:
                super().action_cursor_down()

    def action_cursor_up(self) -> None:
        self._set_hover_cursor(False)
        if self.cursor_coordinate.row == 0 and self.cursor_vertical_escape:
            self.screen.focus_previous()
        else:
            cursor_type = self.cursor_type
            if self.show_cursor and (cursor_type == "cell" or cursor_type == "row"):
                row, column = self.cursor_coordinate
                if row == 0:
                    self.cursor_coordinate = Coordinate(self.row_count - 1, column)
                else:
                    self.cursor_coordinate = self.cursor_coordinate.up()
            else:
                super().action_cursor_up()

    @on(RowsRemoved)
    @on(RowsAdded)
    def _on_rows_removed(self, event: RowsRemoved | RowsAdded) -> None:
        self.set_class(self.row_count == 0, "empty")

    def action_remove_row(self) -> None:
        try:
            cursor_cell_key = self.coordinate_to_cell_key(self.cursor_coordinate)
            cursor_row_key, _ = cursor_cell_key
            self.remove_row(cursor_row_key)
        except CellDoesNotExist:
            pass

    def action_toggle_row(self) -> None:
        try:
            cursor_cell_key = self.coordinate_to_cell_key(self.cursor_coordinate)
            cursor_row_key, _ = cursor_cell_key
            checkbox: PostingDataTable.Checkbox = self.get_cell(cursor_row_key, "checkbox")
            checkbox.toggle()
            # HACK: Without such increment, the table is refreshed
            # only when focus changes to another column.
            self._update_count += 1
            self.refresh()
        except CellDoesNotExist:
            pass

    def __rich_repr__(self):
        yield "id", self.id
        yield "classes", self.classes
        yield "row_count", self.row_count
