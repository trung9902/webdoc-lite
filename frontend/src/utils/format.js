/** Số kiểu Việt Nam trong đề: 9 378,5 (dấu cách ngăn hàng nghìn, dấu phẩy thập phân). */
export const formatNumber = (value, maxFraction = 1) =>
  Number(value)
    .toLocaleString('fr-FR', { maximumFractionDigits: maxFraction })
    .replace(/[  ]/g, ' ');

export const formatDateTime = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  const p = (n) => String(n).padStart(2, '0');

  return `${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}`;
};
