import { SignIn as ClerkSignIn } from '@clerk/react';

export default function SignIn() {
  return <ClerkSignIn routing="hash" signUpUrl="/sign-up" fallbackRedirectUrl="/" />;
}
