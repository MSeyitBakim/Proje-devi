import { describe, expect, it } from 'vitest';
import { pageCount, pageWindow } from './pagination';

describe('pagination helpers', () => {
  it('counts pages', () => {
    expect(pageCount(0, 10)).toBe(1);
    expect(pageCount(21, 10)).toBe(3);
  });
  it('builds a compact window', () => {
    expect(pageWindow(1, 1)).toEqual([1]);
    expect(pageWindow(5, 20)).toEqual([1, '…', 4, 5, 6, '…', 20]);
    expect(pageWindow(2, 4)).toEqual([1, 2, 3, 4]);
  });
});
