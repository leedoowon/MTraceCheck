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

/* readtokens.h -- Functions for reading tokens from an input stream.

   Copyright (C) 1990-1991, 1999, 2001-2004, 2009-2016 Free Software
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
   along with this program.  If not, see <http://www.gnu.org/licenses/>.

   Written by Jim Meyering. */

#ifndef READTOKENS_H
# define READTOKENS_H

# include <stdio.h>

struct tokenbuffer
{
  size_t size;
  char *buffer;
};
typedef struct tokenbuffer token_buffer;

void init_tokenbuffer (token_buffer *tokenbuffer);

size_t
  readtoken (FILE *stream, const char *delim, size_t n_delim,
             token_buffer *tokenbuffer);
size_t
  readtokens (FILE *stream, size_t projected_n_tokens,
              const char *delim, size_t n_delim,
              char ***tokens_out, size_t **token_lengths);

#endif /* not READTOKENS_H */
