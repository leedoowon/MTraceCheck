/**************************************************************************
 *
 * MTraceCheck
 * Copyright 2017 The Regents of the University of Michigan
 * Doowon Lee and Valeria Bertacco
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 *************************************************************************/

/* xalloc-oversized.h -- memory allocation size checking

   Copyright (C) 1990-2000, 2003-2004, 2006-2016 Free Software Foundation, Inc.

   This program is free software: you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation; either version 3 of the License, or
   (at your option) any later version.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program.  If not, see <http://www.gnu.org/licenses/>.  */

#ifndef XALLOC_OVERSIZED_H_
#define XALLOC_OVERSIZED_H_

#include <stddef.h>

#ifndef __has_builtin
# define __has_builtin(x) 0
#endif

/* Return 1 if an array of N objects, each of size S, cannot exist due
   to size arithmetic overflow.  S must be positive and N must be
   nonnegative.  This is a macro, not a function, so that it
   works correctly even when SIZE_MAX < N.

   By gnulib convention, SIZE_MAX represents overflow in size
   calculations, so the conservative dividend to use here is
   SIZE_MAX - 1, since SIZE_MAX might represent an overflowed value.
   However, malloc (SIZE_MAX) fails on all known hosts where
   sizeof (ptrdiff_t) <= sizeof (size_t), so do not bother to test for
   exactly-SIZE_MAX allocations on such hosts; this avoids a test and
   branch when S is known to be 1.  */
#if 5 <= __GNUC__ || __has_builtin (__builtin_mul_overflow)
# define xalloc_oversized(n, s) \
    ({ size_t __xalloc_size; __builtin_mul_overflow (n, s, &__xalloc_size); })
#else
# define xalloc_oversized(n, s) \
    ((size_t) (sizeof (ptrdiff_t) <= sizeof (size_t) ? -1 : -2) / (s) < (n))
#endif

#endif /* !XALLOC_OVERSIZED_H_ */
