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

/* Report a memory allocation failure and exit.

   Copyright (C) 1997-2000, 2002-2004, 2006, 2009-2016 Free Software
   Foundation, Inc.

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

#include <config.h>

#include "xalloc.h"

#include <stdlib.h>

#include "error.h"
//#include "exitfail.h"  // doowon

//#include "gettext.h"  // doowon
#define _(msgid) gettext (msgid)

void
xalloc_die (void)
{
  //error (exit_failure, 0, "%s", _("memory exhausted"));  // doowon, commented out

  /* _Noreturn cannot be given to error, since it may return if
     its first argument is 0.  To help compilers understand the
     xalloc_die does not return, call abort.  Also, the abort is a
     safety feature if exit_failure is 0 (which shouldn't happen).  */
  abort ();
}
