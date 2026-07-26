import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import clsx from 'clsx';

export interface Column<Row> {
  key: string;
  header: string;
  render: (row: Row) => ReactNode;
  /** Value used for sorting; omit to make the column unsortable. */
  sortValue?: (row: Row) => number | string;
  align?: 'left' | 'right';
  /** Numeric/tag columns are monospaced. Prose columns are not. */
  mono?: boolean;
  className?: string;
}

interface DataTableProps<Row> {
  columns: Column<Row>[];
  rows: Row[];
  rowKey: (row: Row) => string | number;
  initialSort?: { key: string; direction: 'asc' | 'desc' };
  isHighlighted?: (row: Row) => boolean;
  onRowClick?: (row: Row) => void;
  maxHeight?: string;
  emptyMessage?: string;
}

/**
 * Dense console log table: uppercase letter-spaced headers, hairline rules,
 * monospaced values, no zebra striping. Shared by every tabular readout in the
 * app so alignment and sorting behave identically everywhere.
 */
export function DataTable<Row>({
  columns,
  rows,
  rowKey,
  initialSort,
  isHighlighted,
  onRowClick,
  maxHeight,
  emptyMessage = 'No records.',
}: DataTableProps<Row>) {
  const [sort, setSort] = useState(initialSort ?? null);

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const column = columns.find((c) => c.key === sort.key);
    if (!column?.sortValue) return rows;
    const direction = sort.direction === 'asc' ? 1 : -1;
    return [...rows].sort((a, b) => {
      const left = column.sortValue!(a);
      const right = column.sortValue!(b);
      if (typeof left === 'number' && typeof right === 'number') {
        return (left - right) * direction;
      }
      return String(left).localeCompare(String(right)) * direction;
    });
  }, [rows, sort, columns]);

  const toggleSort = (key: string) => {
    setSort((current) =>
      current?.key === key
        ? { key, direction: current.direction === 'asc' ? 'desc' : 'asc' }
        : { key, direction: 'asc' },
    );
  };

  if (rows.length === 0) {
    return (
      <p className="border border-hmi-line bg-hmi-panel py-6 text-center font-mono text-micro uppercase text-hmi-dim">
        {emptyMessage}
      </p>
    );
  }

  return (
    <div
      className="overflow-auto rounded-panel border border-hmi-line bg-hmi-panel"
      style={maxHeight ? { maxHeight } : undefined}
    >
      <table className="w-full border-collapse text-left">
        <thead className="sticky top-0 z-10 bg-hmi-header">
          <tr>
            {columns.map((column) => {
              const sortable = Boolean(column.sortValue);
              const active = sort?.key === column.key;
              return (
                <th
                  key={column.key}
                  scope="col"
                  aria-sort={
                    active ? (sort!.direction === 'asc' ? 'ascending' : 'descending') : 'none'
                  }
                  className={clsx(
                    'whitespace-nowrap border-b border-hmi-bezel px-4 py-2 text-tag uppercase text-hmi-label',
                    column.align === 'right' ? 'text-right' : 'text-left',
                  )}
                >
                  {sortable ? (
                    <button
                      type="button"
                      onClick={() => toggleSort(column.key)}
                      className={clsx(
                        'inline-flex items-center gap-1 transition-colors hover:text-hmi-text',
                        active && 'text-signal',
                      )}
                    >
                      {column.header}
                      <span aria-hidden="true" className="font-mono text-micro">
                        {active ? (sort!.direction === 'asc' ? '▲' : '▼') : '·'}
                      </span>
                    </button>
                  ) : (
                    column.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => {
            const highlighted = isHighlighted?.(row) ?? false;
            return (
              <tr
                key={rowKey(row)}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                className={clsx(
                  'border-b border-hmi-line/70 transition-colors last:border-0',
                  onRowClick && 'cursor-pointer',
                  highlighted
                    ? 'bg-signal-fill shadow-[inset_2px_0_0_0_#2DD4BF]'
                    : 'hover:bg-hmi-header/70',
                )}
              >
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={clsx(
                      'whitespace-nowrap px-4 py-2 text-caption text-hmi-text',
                      column.align === 'right' ? 'text-right' : 'text-left',
                      column.mono && 'font-mono',
                      column.className,
                    )}
                  >
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
