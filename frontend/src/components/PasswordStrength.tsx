import React from 'react';

interface PasswordStrengthProps {
  password?: string;
  onValidationChange?: (isValid: boolean) => void;
}

export default function PasswordStrength({ password = "", onValidationChange }: PasswordStrengthProps) {
  const requirements = [
    { label: "At least 8 characters", check: (p: string) => p.length >= 8 },
    { label: "At least one uppercase letter", check: (p: string) => /[A-Z]/.test(p) },
    { label: "At least one lowercase letter", check: (p: string) => /[a-z]/.test(p) },
    { label: "At least one number", check: (p: string) => /[0-9]/.test(p) },
    { label: "At least one symbol", check: (p: string) => /[^A-Za-z0-9]/.test(p) },
  ];

  const checks = requirements.map(req => req.check(password));
  const allValid = checks.every(Boolean);

  React.useEffect(() => {
    if (onValidationChange) {
      onValidationChange(allValid);
    }
  }, [allValid, onValidationChange]);

  if (!password) return null;

  return (
    <div className="mt-2 space-y-1.5 p-3 bg-[#111118] border border-gray-800 rounded-xl">
      <p className="text-xs font-medium text-gray-400 mb-2">Password Requirements:</p>
      {requirements.map((req, index) => {
        const isValid = checks[index];
        return (
          <div key={index} className="flex items-center gap-2">
            <svg 
              className={`w-4 h-4 ${isValid ? "text-green-500" : "text-gray-600"}`} 
              fill="none" viewBox="0 0 24 24" stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <span className={`text-xs ${isValid ? "text-green-400" : "text-gray-500"}`}>
              {req.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}
