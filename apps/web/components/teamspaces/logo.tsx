/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { MembersOutline } from "@makeplane/propel/icons";
import { Logo } from "@plane/blocks/emoji-icon-picker";
import type { TLogoProps } from "@plane/types";

type Props = {
  logo: TLogoProps | undefined;
  size?: number;
};

/** A teamspace's emoji/icon, or the generic teamspace icon when none has been picked. */
export function TeamspaceLogo({ logo, size = 16 }: Props) {
  if (!logo?.in_use) return <MembersOutline className="shrink-0 text-tertiary" width={size} height={size} />;
  return <Logo logo={logo} size={size} />;
}
