/** Logo trung tính của WebDoc Lite (thay bằng logo của bạn). `light` = bản trắng dùng trên nền tối. */
const Logo = ({ size = 'medium', light = false }) => {
  const { width, height } = size === 'small' ? { width: 60, height: 50 } : { width: 64, height: 64 };
  const ink = light ? '#ffffff' : '#8b070a';
  const paper = light ? 'transparent' : '#ffffff';

  return (
    <svg width={width} height={height} viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="WebDoc">
      <circle cx="32" cy="32" r="29" stroke={ink} strokeWidth="4" fill={paper} />
      <path d="M22 19h14l8 8v18a2 2 0 0 1-2 2H22a2 2 0 0 1-2-2V21a2 2 0 0 1 2-2Z" stroke={ink} strokeWidth="3" strokeLinejoin="round" />
      <path d="M36 19v8h8M25 33h14M25 39h14" stroke={ink} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
};

export default Logo;
