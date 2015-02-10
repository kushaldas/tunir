Why another CI?
================

I have used Jenkins before. I was maintaining one instance in one of my vps
instance.  The amount of ram required by Jenkins was too much for my small vm.
I can admit that I am not a great sys-admin anyway.

As part of my daily job, I have to test the latest cloud images we build under
Fedora project, while doing so I figured out that most of it can be automated
if we have a system to create/maintain/terminate cloud instances. Of course I
do not want any actual cloud, it will be a different monster to maintain.

This is the point where I came up with Tunir, this simple CI system will help
me to do automated tests for the cloud images. I kept the system generic enough
to execute any kind of tests people want.

The configuration is very bare minimal with Tunir. The only time you may have
to do some real work, if you are using Docker containers to execute the test.
