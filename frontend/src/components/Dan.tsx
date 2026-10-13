/**
 * Handsome Dan, carried over from HW 4 — the shop's bulldog, now asleep under
 * the back-office desk. He wakes when the team is working.
 *
 * Continuity matters: the storefront and the operations desk are the same
 * business, and the mascot is the cheapest, clearest way to say so. He also
 * gives the idle state something to be other than blank.
 */
export default function Dan({ awake = false, size = 92 }: { awake?: boolean; size?: number }) {
  return (
    <svg width={size} height={size * 0.78} viewBox="0 0 120 94" aria-hidden="true"
         style={{ overflow: "visible" }}>
      {/* drifting z's while he sleeps */}
      {!awake && (
        <g fill="var(--ink-soft)" fontFamily="var(--font-display)" opacity=".55">
          <text x="92" y="26" fontSize="13">
            z<animate attributeName="opacity" values="0;1;0" dur="3s" repeatCount="indefinite" />
            <animateTransform attributeName="transform" type="translate" values="0 0;6 -14" dur="3s" repeatCount="indefinite" />
          </text>
          <text x="86" y="36" fontSize="10">
            z<animate attributeName="opacity" values="0;1;0" dur="3s" begin="1s" repeatCount="indefinite" />
            <animateTransform attributeName="transform" type="translate" values="0 0;5 -12" dur="3s" begin="1s" repeatCount="indefinite" />
          </text>
        </g>
      )}
      {/* body */}
      <ellipse cx="58" cy="70" rx="40" ry="20" fill="var(--dan-fur, #f0e2c4)" stroke="var(--ink)" strokeWidth="2.2" />
      <ellipse cx="58" cy="76" rx="32" ry="11" fill="var(--dan-shade, #d8c49b)" opacity=".5" />
      {/* head */}
      <g>
        {awake && (
          <animateTransform attributeName="transform" type="rotate"
                            values="0 44 44;-4 44 44;0 44 44;4 44 44;0 44 44" dur="3.2s" repeatCount="indefinite" />
        )}
        <ellipse cx="44" cy="44" rx="27" ry="24" fill="var(--dan-fur, #f0e2c4)" stroke="var(--ink)" strokeWidth="2.2" />
        {/* ears */}
        <path d="M22 28 q-9 -5 -11 7 q-1 10 9 11 z" fill="var(--dan-shade,#d8c49b)" stroke="var(--ink)" strokeWidth="2" />
        <path d="M66 28 q9 -5 11 7 q1 10 -9 11 z" fill="var(--dan-shade,#d8c49b)" stroke="var(--ink)" strokeWidth="2" />
        {/* muzzle */}
        <ellipse cx="44" cy="54" rx="17" ry="12" fill="var(--dan-muzzle, #fdf6e6)" stroke="var(--ink)" strokeWidth="1.8" />
        <path d="M38 58 q6 5 12 0" stroke="var(--ink)" strokeWidth="2" fill="none" strokeLinecap="round" />
        <ellipse cx="44" cy="47" rx="5" ry="3.6" fill="var(--ink)" />
        {/* eyes: shut when asleep */}
        {awake ? (
          <>
            <circle cx="34" cy="38" r="3.4" fill="var(--ink)" />
            <circle cx="54" cy="38" r="3.4" fill="var(--ink)" />
            <circle cx="35.2" cy="36.8" r="1.1" fill="#fff" />
            <circle cx="55.2" cy="36.8" r="1.1" fill="#fff" />
          </>
        ) : (
          <>
            <path d="M30 38 q4 3 8 0" stroke="var(--ink)" strokeWidth="2" fill="none" strokeLinecap="round" />
            <path d="M50 38 q4 3 8 0" stroke="var(--ink)" strokeWidth="2" fill="none" strokeLinecap="round" />
          </>
        )}
        {/* brow wrinkles, the bulldog tell */}
        <path d="M31 29 q5 -3 10 -1 M47 28 q5 -2 10 1" stroke="var(--ink)" strokeWidth="1.6" fill="none" strokeLinecap="round" opacity=".7" />
      </g>
      {/* collar */}
      <rect x="30" y="62" width="28" height="7" rx="3" fill="var(--crimson)" stroke="var(--ink)" strokeWidth="1.8" />
      <circle cx="44" cy="71" r="4" fill="var(--gold)" stroke="var(--ink)" strokeWidth="1.6" />
      {/* tail wag when awake */}
      <path d="M96 66 q10 -6 7 -16" stroke="var(--ink)" strokeWidth="3" fill="none" strokeLinecap="round">
        {awake && <animate attributeName="d" values="M96 66 q10 -6 7 -16;M96 66 q12 -2 14 -12;M96 66 q10 -6 7 -16" dur=".7s" repeatCount="indefinite" />}
      </path>
    </svg>
  );
}
