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

/* tsort - topological sort.
   Copyright (C) 1998-2016 Free Software Foundation, Inc.

   This program is free software: you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation, either version 3 of the License, or
   (at your option) any later version.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program.  If not, see <http://www.gnu.org/licenses/>.  */

/* Written by Mark Kettenis <kettenis@phys.uva.nl>.  */

/* The topological sort is done according to Algorithm T (Topological
   sort) in Donald E. Knuth, The Art of Computer Programming, Volume
   1/Fundamental Algorithms, page 262.  */

#include <config.h>

#include <assert.h>
#include <getopt.h>
#include <sys/types.h>

//#include "system.h"
//#include "long-options.h"
//#include "error.h"
#include "fadvise.h"
#include "readtokens.h"
//#include "stdio--.h"
//#include "quote.h"

#include <stdio.h>
#include <sys/time.h>
#include "xalloc.h"

/* Debugging message */
//#define DEBUG
#ifdef DEBUG
#define debug(...) printf(__VA_ARGS__)
#else
#define debug(...) /* empty */
#endif

#ifdef DEBUG_OLD
#define debug_old(...) printf(__VA_ARGS__)
#else
#define debug_old(...) /* empty */
#endif

/* Assertion statement */
#ifdef TIME_MEASURE
#define debug_assert(...) /* empty */
#else
#define debug_assert(...) assert(__VA_ARGS__)
#endif

/* Basic type definitions */
#define bool signed char
#define true 1
#define false 0
#define EXIT_SUCCESS 0
#define EXIT_FAILURE 1
#define IF_LINT(Code)  /* empty */
#define _GL_UNUSED __attribute__ ((__unused__))
#define STREQ(a, b) (strcmp (a, b) == 0)

/* The official name of this program (e.g., no 'g' prefix).  */
#define PROGRAM_NAME "tsort"

#define AUTHORS proper_name ("Mark Kettenis")

/* Token delimiters when reading from a file.  */
#define DELIM " \t\n"

/* Members of the list of successors.  */
struct successor
{
  struct item *suc;
  struct successor *next;
};

/* Each string is held in core as the head of a list of successors.  */
struct item
{
  const char *str;
  bool visited;  /* doowon */
  struct item *left, *right;
  int balance; /* -1, 0, or +1 */
  size_t count;
  struct item *qlink;
  struct successor *top;
#ifdef DIFF
  int order;
#endif
};

/* The head of the sorted list.  */
static struct item *head = NULL;

/* The tail of the list of 'zeros', strings that have no predecessors.  */
static struct item *zeros = NULL;

/* Used for loop detection.  */
static struct item *loop = NULL;

/* The number of strings to sort.  */
static size_t n_strings = 0;

/* Below are doowon's modification for multi-execution support */
struct dependency
{
  // a -> b
  struct item *a;
  struct item *b;
  struct dependency *next_dep;
};

struct execution
{
  int exec_index;
  struct dependency *dep;
  struct execution *next_exec;
};

static size_t const_n_strings;
//size_t zero_count;
//size_t clear_count;
struct item **topo_order;

static bool
clear_relation (struct item *k)
{
#ifdef FREE_SUCCESSOR
  struct successor *p;
  p = k->top;
  while (p != NULL)
    {
      struct successor *next_p;
      next_p = p->next;
      free (p);
      p = next_p;
    }  
#endif
  k->visited = (k->str ? false : true);
  k->count = 0;
  k->qlink = NULL; /* Is this statement necessary? */
  k->top = NULL;
  //clear_count++; // FIXME: delete it
  return false;
}

/*
void
usage (int status)
{
  if (status != EXIT_SUCCESS)
    emit_try_help ();
  else
    {
      printf (_("\
Usage: %s [OPTION] [FILE]\n\
Write totally ordered list consistent with the partial ordering in FILE.\n\
"), program_name);

      emit_stdin_note ();

      fputs (_("\
\n\
"), stdout);
      fputs (HELP_OPTION_DESCRIPTION, stdout);
      fputs (VERSION_OPTION_DESCRIPTION, stdout);
      emit_ancillary_info (PROGRAM_NAME);
    }

  exit (status);
}
*/

/* Create a new item/node for STR.  */
static struct item *
new_item (const char *str)
{
  struct item *k = xmalloc (sizeof *k);

  k->str = (str ? xstrdup (str): NULL);
  k->visited = (str ? false : true);
  k->left = k->right = NULL;
  k->balance = 0;

  /* T1. Initialize (COUNT[k] <- 0 and TOP[k] <- ^).  */
  k->count = 0;
  k->qlink = NULL;
  k->top = NULL;

#ifdef DIFF
  k->order = -1; // probably this is not necessary
#endif

  return k;
}

/* Search binary tree rooted at *ROOT for STR.  Allocate a new tree if
   *ROOT is NULL.  Insert a node/item for STR if not found.  Return
   the node/item found/created for STR.

   This is done according to Algorithm A (Balanced tree search and
   insertion) in Donald E. Knuth, The Art of Computer Programming,
   Volume 3/Searching and Sorting, pages 455--457.  */

static struct item *
search_item (struct item *root, const char *str)
{
  struct item *p, *q, *r, *s, *t;
  int a;

  debug_assert (root);

  /* Make sure the tree is not empty, since that is what the algorithm
     below expects.  */
  if (root->right == NULL)
    return (root->right = new_item (str));

  /* A1. Initialize.  */
  t = root;
  s = p = root->right;

  while (true)
    {
      /* A2. Compare.  */
      a = strcmp (str, p->str);
      if (a == 0)
        return p;

      /* A3 & A4.  Move left & right.  */
      if (a < 0)
        q = p->left;
      else
        q = p->right;

      if (q == NULL)
        {
          /* A5. Insert.  */
          q = new_item (str);

          /* A3 & A4.  (continued).  */
          if (a < 0)
            p->left = q;
          else
            p->right = q;

          /* A6. Adjust balance factors.  */
          debug_assert (!STREQ (str, s->str));
          if (strcmp (str, s->str) < 0)
            {
              r = p = s->left;
              a = -1;
            }
          else
            {
              r = p = s->right;
              a = 1;
            }

          while (p != q)
            {
              debug_assert (!STREQ (str, p->str));
              if (strcmp (str, p->str) < 0)
                {
                  p->balance = -1;
                  p = p->left;
                }
              else
                {
                  p->balance = 1;
                  p = p->right;
                }
            }

          /* A7. Balancing act.  */
          if (s->balance == 0 || s->balance == -a)
            {
              s->balance += a;
              return q;
            }

          if (r->balance == a)
            {
              /* A8. Single Rotation.  */
              p = r;
              if (a < 0)
                {
                  s->left = r->right;
                  r->right = s;
                }
              else
                {
                  s->right = r->left;
                  r->left = s;
                }
              s->balance = r->balance = 0;
            }
          else
            {
              /* A9. Double rotation.  */
              if (a < 0)
                {
                  p = r->right;
                  r->right = p->left;
                  p->left = r;
                  s->left = p->right;
                  p->right = s;
                }
              else
                {
                  p = r->left;
                  r->left = p->right;
                  p->right = r;
                  s->right = p->left;
                  p->left = s;
                }

              s->balance = 0;
              r->balance = 0;
              if (p->balance == a)
                s->balance = -a;
              else if (p->balance == -a)
                r->balance = a;
              p->balance = 0;
            }

          /* A10. Finishing touch.  */
          if (s == t->right)
            t->right = p;
          else
            t->left = p;

          return q;
        }

      /* A3 & A4.  (continued).  */
      if (q->balance)
        {
          t = p;
          s = q;
        }

      p = q;
    }

  /* NOTREACHED */
}

/* Record the fact that J precedes K.  */

static void
record_relation (struct item *j, struct item *k)
{
  struct successor *p;

  if (!STREQ (j->str, k->str))
    {
      k->count++;
      p = xmalloc (sizeof *p);  // FIXME: Modify this to static allocation
      p->suc = k;
      p->next = j->top;
      j->top = p;
    }
}

static bool
count_items (struct item *unused _GL_UNUSED)
{
  n_strings++;
  return false;
}

static bool
scan_zeros (struct item *k)
{
  /* Ignore strings that have already been printed.  */
  //if (k->count == 0 && k->str)
  if (k->count == 0 && !k->visited)  // doowon
    {
      if (head == NULL)
        head = k;
      else
        zeros->qlink = k;

      zeros = k;

      // FIXME: delete below
      //zero_count++;
    }

  return false;
}

/* Try to detect the loop.  If we have detected that K is part of a
   loop, print the loop on standard error, remove a relation to break
   the loop, and return true.

   The loop detection strategy is as follows: Realise that what we're
   dealing with is essentially a directed graph.  If we find an item
   that is part of a graph that contains a cycle we traverse the graph
   in backwards direction.  In general there is no unique way to do
   this, but that is no problem.  If we encounter an item that we have
   encountered before, we know that we've found a cycle.  All we have
   to do now is retrace our steps, printing out the items until we
   encounter that item again.  (This is not necessarily the item that
   we started from originally.)  Since the order in which the items
   are stored in the tree is not related to the specified partial
   ordering, we may need to walk the tree several times before the
   loop has completely been constructed.  If the loop was found, the
   global variable LOOP will be NULL.  */

static bool
detect_loop (struct item *k)
{
  if (k->count > 0)
    {
      /* K does not have to be part of a cycle.  It is however part of
         a graph that contains a cycle.  */

      if (loop == NULL)
        /* Start traversing the graph at K.  */
        loop = k;
      else
        {
          struct successor **p = &k->top;

          while (*p)
            {
              if ((*p)->suc == loop)
                {
                  if (k->qlink)
                    {
                      /* We have found a loop.  Retrace our steps.  */
                      while (loop)
                        {
                          struct item *tmp = loop->qlink;

                          //error (0, 0, "%s", (loop->str));  // doowon, commented out

                          /* Until we encounter K again.  */
                          if (loop == k)
                            {
                              /* Remove relation.  */
                              (*p)->suc->count--;
                              *p = (*p)->next;
                              break;
                            }

                          /* Tidy things up since we might have to
                             detect another loop.  */
                          loop->qlink = NULL;
                          loop = tmp;
                        }

                      while (loop)
                        {
                          struct item *tmp = loop->qlink;

                          loop->qlink = NULL;
                          loop = tmp;
                        }

                      /* Since we have found the loop, stop walking
                         the tree.  */
                      return true;
                    }
                  else
                    {
                      k->qlink = loop;
                      loop = k;
                      break;
                    }
                }

              p = &(*p)->next;
            }
        }
    }

  return false;
}

/* Recurse (sub)tree rooted at ROOT, calling ACTION for each node.
   Stop when ACTION returns true.  */

static bool
recurse_tree (struct item *root, bool (*action) (struct item *))
{
  if (root->left == NULL && root->right == NULL)
    return (*action) (root);
  else
    {
      if (root->left != NULL)
        if (recurse_tree (root->left, action))
          return true;
      if ((*action) (root))
        return true;
      if (root->right != NULL)
        if (recurse_tree (root->right, action))
          return true;
    }

  return false;
}

/* Walk the tree specified by the head ROOT, calling ACTION for
   each node.  */

static void
walk_tree (struct item *root, bool (*action) (struct item *))
{
  if (root->right)
    recurse_tree (root->right, action);
}

/* Do a topological sort on FILE.   Return true if successful.  */

static bool
tsort (const char *file)
{
  bool ok = true;
  struct item *root;
  struct item *j = NULL;
  struct item *k = NULL;
  token_buffer tokenbuffer;
  bool is_stdin = STREQ (file, "-");
  struct execution *exec_head = NULL;
  struct execution *exec_curr = NULL;
#ifdef DIFF
  struct execution *exec_prev = NULL;
#endif
  int curr_exec_index = 0;
  FILE *fp_list = NULL;
#ifdef DIFF
  int order_count = 0;
  int leading_index;
  int trailing_index;
#endif
  struct timeval start_time, end_time;
  unsigned long long elapsed_time;

  /* Intialize the head of the tree will hold the strings we're sorting.  */
  root = new_item (NULL);

  /* doowon: Read a list of files to be processed */
  debug_old ("tsort(): calling init_tokenbuffer()\n");
  init_tokenbuffer (&tokenbuffer);

  fp_list = fopen(file, "r");

  // Read all executions
  while (1)
    {
      struct dependency *dep_curr = NULL;
      size_t len = readtoken (fp_list, DELIM, sizeof (DELIM) - 1, &tokenbuffer);
      if (len == (size_t) -1)
        break;

      debug_assert (len != 0);

      debug_old ("tokenbuffer.buffer (file list): %s\n", tokenbuffer.buffer);
      if (! freopen (tokenbuffer.buffer, "r", stdin))
        {
          printf ("Error: cannot open %s\n", file);
          assert (false);
        }

      if (exec_curr != NULL)
        {
          debug_assert (exec_head != NULL);
          exec_curr->next_exec = xmalloc (sizeof *exec_curr);
          exec_curr = exec_curr->next_exec;
        }
      else
        {
          exec_curr = xmalloc (sizeof *exec_curr);
          exec_head = exec_curr;
        }
      exec_curr->exec_index = curr_exec_index++;
      exec_curr->dep = NULL;
      exec_curr->next_exec = NULL;

      j = NULL;
      k = NULL;
      while (1)
        {
          debug_old ("tsort(): reading a relation from file\n");

          /* T2. Next Relation.  */
          size_t len = readtoken (stdin, DELIM, sizeof (DELIM) - 1, &tokenbuffer);
          if (len == (size_t) -1)
            break;

          debug_assert (len != 0);

          debug_old ("tokenbuffer.buffer (relation): %s\n", tokenbuffer.buffer);

          // FIXME: string -> integer
          k = search_item (root, tokenbuffer.buffer);

          if (j)
            {
              if (dep_curr != NULL)
                {
                  debug_assert (exec_curr->dep != NULL);
                  dep_curr->next_dep = xmalloc (sizeof *dep_curr);
                  dep_curr = dep_curr->next_dep;
                }
              else
                {
                  dep_curr = xmalloc (sizeof *dep_curr);
                  exec_curr->dep = dep_curr;
                }

              debug_old ("allocating dependency data structure: 0x%lx (0x%lx->0x%lx)\n", (unsigned long) dep_curr, (unsigned long) j, (unsigned long) k);
              dep_curr->a = j;
              dep_curr->b = k;
              dep_curr->next_dep = NULL;
              k = NULL;
            }
          j = k;
        }
      if (k != NULL)
        {
          printf ("Error: input contains an odd number of tokens\n");
          assert (false);
        }

      // doowon, relocated from the end of function
      if (fclose (stdin) != 0)
        {
          printf ("Error: cannot close\n");
          assert (false);
        }
    }

  if (fclose (fp_list) != 0)
    {
      printf ("Error: cannot close list file\n");
      assert (false);
    }

  gettimeofday (&start_time, NULL);

  debug ("tsort(): number of executions %d\n", curr_exec_index);

  /* T1. Initialize (N <- n).  */
  debug ("tsort(): calling walk_tree(count_items)\n");
  walk_tree (root, count_items);
  const_n_strings = n_strings;  // doowon, store number of nodes in the tree
  debug ("tsort(): n_strings(1) %d\n", n_strings);
#ifdef DIFF
  topo_order = (struct item **) malloc (n_strings * sizeof(struct item *));
#endif

  curr_exec_index = 0;
  exec_curr = exec_head;
  while (exec_curr != NULL)
    {
#if !defined(TIME_MEASURE) && !defined(RESORT_MEASURE)
      printf ("tsort(): start execution %d\n", curr_exec_index);
#endif
#ifdef DIFF
      if (curr_exec_index == 0)
        {
#ifdef RESORT_MEASURE
          printf ("A,%d,%d,%d,%d\n", curr_exec_index, const_n_strings, 0, const_n_strings);
#endif
#endif
          struct dependency *curr_dep = exec_curr->dep;
          //debug_assert (curr_dep != NULL);
          while (curr_dep != NULL)
            {
              j = curr_dep->a;
              k = curr_dep->b;
              debug_old ("record relations from data structure: 0x%lx (0x%lx->0x%lx)\n",\
                    (unsigned long) curr_dep, (unsigned long) j, (unsigned long) k);
              /* T3. Record the relation.  */
              record_relation (j, k);
              curr_dep = curr_dep->next_dep;
            }
#ifdef DIFF
          debug_assert (order_count == 0);
        }
      else
        {
          struct dependency *curr_dep = exec_curr->dep;
          struct dependency *prev_dep = exec_prev->dep;
          bool skip_exec = true;
          /* Diffing step 1: Detecting skip condition */
          while (curr_dep != NULL)
            {
              struct item *prev_j = prev_dep->a;
              struct item *prev_k = prev_dep->b;
              j = curr_dep->a;
              k = curr_dep->b;
              if (j == prev_j && k == prev_k)
                {
                  debug_assert (j->order < k->order);
                  ; // nothing to do
                }
              else if (j == prev_j)
                {
                  // Change "B"
                  struct successor *curr_suc = prev_j->top;
                  bool replaced = false; // FIXME: debug
                  while (curr_suc != NULL)
                    {
                      if (curr_suc->suc == prev_k)
                        {
                          curr_suc->suc = k;
                          replaced = true;
                          break;
                        }
                      curr_suc = curr_suc->next;
                    }
                  debug_assert (replaced);
                }
              else if (k == prev_k)
                {
                  // Change "A"
                  struct successor *curr_suc = prev_j->top;
                  struct successor *prev_suc = NULL;
                  bool removed = false; // FIXME: debug
                  while (true)
                    {
                      if (curr_suc->suc == prev_k)
                        {
                          if (prev_suc == NULL)
                            prev_j->top = prev_j->top->next;
                          else
                            prev_suc->next = curr_suc->next;
                          removed = true;
                          break;
                        }
                      prev_suc = curr_suc;
                      curr_suc = curr_suc->next;
                    }
                  debug_assert (removed);
                  // Step 2: Add new successor
                  struct successor *p = xmalloc (sizeof *p);
                  p->suc = k;
                  p->next = j->top;
                  j->top = p;
                }
              else
                {
                  /* Should not reach here */
                  assert (false);
                }
              if (j->order > k->order)
                skip_exec = false;
              curr_dep = curr_dep->next_dep;
              prev_dep = prev_dep->next_dep;
            } // while (curr_dep != NULL)
          if (skip_exec)
            {
#if !defined(TIME_MEASURE) && !defined(RESORT_MEASURE)
              printf ("skipping execution %d\n", curr_exec_index);
#endif
#ifdef RESORT_MEASURE
              printf ("B,%d,%d,%d,%d\n", curr_exec_index, const_n_strings, -1, -1);
#endif
              exec_prev = exec_curr;
              exec_curr = exec_curr->next_exec;
              curr_exec_index++;
              continue;
            }
          /* Diffing step 2: Find a subgraph boundary */
          leading_index = const_n_strings;
          trailing_index = 0;
          curr_dep = exec_curr->dep;
          while (curr_dep != NULL)
            {
              j = curr_dep->a;
              k = curr_dep->b;
              if (j->order > k->order)
                {
                  if (k->order < leading_index)
                    leading_index = k->order;
                  if (j->order > trailing_index)
                    trailing_index = j->order;
                }
              else
                {
                  debug_assert (j->order < k->order);
                }
              curr_dep = curr_dep->next_dep;
            }
          debug ("exec %d leading %d trailing %d\n",\
              curr_exec_index, leading_index, trailing_index);
          debug_assert (leading_index < trailing_index);
#ifdef RESORT_MEASURE
          printf ("C,%d,%d,%d,%d\n", curr_exec_index, const_n_strings, leading_index, trailing_index);
#endif
          /* Diffing step 3: Scan zeros */
          debug_assert (head == NULL);
          for (order_count = leading_index; order_count <= trailing_index; order_count++)
            {
              // NOTE: recycling 'visited' flag... would it work?
              topo_order[order_count]->visited = false;
              topo_order[order_count]->count = 0;
              topo_order[order_count]->qlink = NULL;
            }
          for (order_count = leading_index; order_count <= trailing_index; order_count++)
            {
              // NOTE: 'count' member variable must be computed after
              //       'visited' flag has been initialized
              struct successor *curr_suc = topo_order[order_count]->top;
              while (curr_suc != NULL)
                {
                  if (!curr_suc->suc->visited)
                    curr_suc->suc->count++;
                  curr_suc = curr_suc->next;
                }
            }
          //zero_count = 0; // FIXME: delete this
          for (order_count = leading_index; order_count <= trailing_index; order_count++)
            {
              if (topo_order[order_count]->count == 0)
                {
                  /* copied from scan_zeros() */
                  if (head == NULL)
                    head = topo_order[order_count];
                  else
                    zeros->qlink = topo_order[order_count];
                  zeros = topo_order[order_count];
                  //zero_count++;  // FIXME: delete this
                }
            }
          //debug ("scan_zeros: %d zeros\n", zero_count); // FIXME: delete this
          n_strings = trailing_index - leading_index + 1;
          order_count = leading_index;
        }  // if (curr_exec_index != 0)
#endif

      debug ("tsort(): n_strings(2) %d\n", n_strings);

#ifdef DIFF
#ifdef DDEBUG
      if (curr_exec_index > 0)
        {
          // FIXME: Delete this for loop
          for (int verify_count = 0; verify_count < const_n_strings; verify_count++)
            {
              debug ("%s ->", topo_order[verify_count]->str);
              struct successor *curr_suc = topo_order[verify_count]->top;
              while (curr_suc)
                {
                  debug (" %s", curr_suc->suc->str);
                  curr_suc = curr_suc->next;
                }
              debug ("\n");
            }
        }
#endif
#endif

      while (n_strings > 0)
        {
          /* T4. Scan for zeros.  */
          //zero_count = 0;  // FIXME: delete this
#ifdef DIFF
          if (curr_exec_index == 0)
            walk_tree (root, scan_zeros);
#else
          walk_tree (root, scan_zeros);
#endif
          //debug ("scan_zeros: %d zeros\n", zero_count); // FIXME: delete this

          while (head)
            {
              struct successor *p = head->top;

              /* T5. Output front of queue.  */
#ifdef DEBUG
              puts (head->str);
#endif
#ifdef lint
              /* suppress valgrind "definitely lost" warnings.  */
              void *head_str = (void *) head->str;
              free (head_str);
#endif
              //head->str = NULL;	/* Avoid printing the same string twice.  */
              head->visited = true;
#ifdef DIFF
              if (curr_exec_index > 0)
                debug_assert (head->order >= leading_index && head->order <= trailing_index);
              head->order = order_count;
              topo_order[order_count] = head;
              order_count++;
#endif
              n_strings--;

              /* T6. Erase relations.  */
              while (p)
                {
                  p->suc->count--;
                  if (p->suc->count == 0)
                    {
                      zeros->qlink = p->suc;
                      zeros = p->suc;
                    }

                  p = p->next;
                }

              /* T7. Remove from queue.  */
              head = head->qlink;
            }

          /* T8.  End of process.  */
          if (n_strings > 0)
            {
              printf ("tsort(): cycle detected!!\n");

              /* The input contains a loop.  */
              //error (0, 0, _("%s: input contains a loop:"), quotef (file));
              // doowon, error message commented out
              ok = false;

              /* Print the loop and remove a relation to break it.  */
              do
                walk_tree (root, detect_loop);
              while (loop);
            }
        }

#ifdef DIFF
#ifdef DEBUG
      if (curr_exec_index > 0)
        {
          debug_assert (order_count == trailing_index+1);
        }
      struct dependency *verify_dep = exec_curr->dep;
      int verify_count = 0;
      while (verify_dep)
        {
          debug_assert (verify_dep->a->order < verify_dep->b->order);
          verify_dep = verify_dep->next_dep;
          verify_count++;
        }
      debug ("tsort(): verified %d dependencies in execution %d\n", verify_count, curr_exec_index);
      for (verify_count = 0; verify_count < const_n_strings; verify_count++)
        {
          debug ("%s ->", topo_order[verify_count]->str);
          struct successor *curr_suc = topo_order[verify_count]->top;
          while (curr_suc)
            {
              debug (" %s", curr_suc->suc->str);
              curr_suc = curr_suc->next;
            }
          debug ("\n");
        }
#endif
#endif

      debug ("tsort(): done analyzing execution %d\n", curr_exec_index);

      // doowon
      if (exec_curr->next_exec == NULL)
        break;

#ifdef DIFF
      exec_prev = exec_curr;
#endif
      exec_curr = exec_curr->next_exec;
#ifndef DIFF
      //clear_count = 0;
      walk_tree (root, clear_relation);
      //debug ("clear_count %d\n", clear_count);
      n_strings = const_n_strings;
#endif
      head = NULL;
      zeros = NULL;  /* Is it necessary? */
      loop = NULL;
      curr_exec_index++;
    }
  IF_LINT (free (root));

#ifdef DIFF
  IF_LINT (free (topo_order));
#endif

  gettimeofday (&end_time, NULL);
  elapsed_time = 1000000 * (end_time.tv_sec - start_time.tv_sec) + (end_time.tv_usec - start_time.tv_usec);
  printf ("### Elapsed time %llu microseconds\n", elapsed_time);

  return ok;
}

int
main (int argc, char **argv)
{
  bool ok;

  //initialize_main (&argc, &argv);
  //set_program_name (argv[0]);
  //setlocale (LC_ALL, "");
  //bindtextdomain (PACKAGE, LOCALEDIR);
  //textdomain (PACKAGE);

  //atexit (close_stdout);

  //parse_long_options (argc, argv, PROGRAM_NAME, PACKAGE, Version,
  //                    usage, AUTHORS, (char const *) NULL);
  //if (getopt_long (argc, argv, "", NULL, NULL) != -1)
  //  usage (EXIT_FAILURE);

  //if (1 < argc - optind)
  //  {
  //    error (0, 0, _("extra operand %s"), quote (argv[optind + 1]));
  //    usage (EXIT_FAILURE);
  //  }

  //ok = tsort (optind == argc ? "-" : argv[optind]);

  debug ("Entering tsort()\n");
  ok = tsort (argv[1]);

  return ok ? EXIT_SUCCESS : EXIT_FAILURE;
}

// vim: et ts=2
