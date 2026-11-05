// SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
// All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import { Suspense } from 'react';
import { ObjectsView } from '@/components/objectsPage/ObjectsView';

// `ObjectsView` reads the selected type and instance from the search params.
export default function ObjectsPage() {
	return (
		<Suspense>
			<ObjectsView />
		</Suspense>
	);
}
