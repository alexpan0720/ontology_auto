// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import type { SVGProps } from 'react';

/** Stands in for every SVGR icon under test. */
const SvgStub = (props: SVGProps<SVGSVGElement>) => <svg data-testid="icon" {...props} />;

export default SvgStub;
