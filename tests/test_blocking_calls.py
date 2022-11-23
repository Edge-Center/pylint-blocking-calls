import astroid
import pylint.testutils

from src.pylint_blocking_calls import helpers
from src.pylint_blocking_calls.blocking_calls import BlockingCallsChecker


class TestBlockingCallsChecker(pylint.testutils.CheckerTestCase):
    CHECKER_CLASS = BlockingCallsChecker

    def setup_method(self):
        super().setup_method()
        self.checker.set_option(
            "blocking-function-names",
            r"^.*auth\.get_auth_ref$,^.*barbican.*\..+$,^.*cinder.*\..+$,^.*glance.*\..+$,^.*heat.*\..+$,^.*ironic.*\..+$,^.*neutron.*\..+$,^.*nova.*\..+$,^.*octavia.*\..+$,^get_session$,^.*session.*\.(commit|delete|rollback|refresh|close)$,^.*session.*\..+\.get$,^requests\.(get|post|put|patch|delete)$,^.+\.(one|one_or_none|all|first)$,^.*keystone.*\.(access_rules|application_credentials|auth|credentials|ec2|endpoint_filter|endpoint_groups|endpoint_policy|endpoints|domain_configs|domains|federation|groups|limits|policies|projects|registered_limits|regions|role_assignments|roles|inference_rules|services|simple_cert|tokens|trusts|users).*$",
        )
        self.checker.set_option("skip-functions", r"^delete_.+$")
        self.checker.set_option(
            "skip-modules",
            r"^src\.db\.task$,^src\.db\.tasks\..+$,^src\.worker\..+$,^src\.tests\..+$",
        )
        self.checker.set_option("skip-decorated", r"^thread$")
        self.checker.linter.current_name = "test_file.py"

    def test_check_unnamed_functions_ignored(self):
        calls = astroid.extract_node(
            """
            lamdbas = [lambda: ...]

            def closure():
                return lambda: ...

            def unnamed_functions_calls():
                lamdbas[0]()  # @
                closure()()  # @
                "".join(["a", "b"])  # @
                [].append(1)  # @
                {i: i for i in range(5)}.get(0)  # @
        """
        )

        with self.assertNoMessages():
            for call in calls:
                self.checker.visit_call(call)
            self.checker.close()

        assert not self.checker._all_visited_calls

    def test_check_blocking_calls_in_functions(self):
        calls = astroid.extract_node(
            """   
            async def async_blocking_function():
                barbican = ...
                barbican.secrets.get()  #@

            def sync_blocking_function():
                barbican = ...
                # blocking-call
                barbican.secrets.get()   #@

            def nested_sync_blocking_function():
                sync_blocking_function()        #@

            async def nested_async_blocking_function():
                # blocking-call
                nested_sync_blocking_function()  #@
        """
        )
        with self.assertAddsMessages(
            pylint.testutils.MessageTest(
                msg_id="blocking-call",
                node=calls[0],
                args=("barbican.secrets.get",),
            ),
            pylint.testutils.MessageTest(
                msg_id="blocking-call",
                node=calls[3],
                args=(
                    "nested_sync_blocking_function -> sync_blocking_function -> barbican.secrets.get",
                ),
            ),
            ignore_position=True,
        ):
            for call in calls:
                self.checker.visit_call(call)
            self.checker.close()

    def test_check_blocking_calls_in_methods(self):
        calls = astroid.extract_node(
            """                   
            def closure():
                return lambda: ...

            def sync_blocking_function():
                barbican = ...
                __(barbican.secrets.get())

            class Object:
                class_property = __(closure())

                @classmethod
                def class_method(cls, arg, *args, kwarg=None, **kwargs):
                    __(print(arg, args, kwarg, kwargs)) 
                    return 5

                @staticmethod
                def static_method(arg, *args, kwarg=None, **kwargs):
                    __(print(arg, kwarg, args, kwargs))
                    return 5

                def object_method(self, arg, *args, kwarg=None, **kwargs):
                    __(self.static_method(arg, *args, kwarg=kwarg, **kwargs))
                    __(print(arg, kwarg, args, kwargs))
                    return 5

                async def object_async_blocking_method(self, arg, *args, kwarg=None, **kwargs):
                    __(print(getattr(self, arg)))
                    __(print(arg, kwarg, args, kwargs))
                    __(self.object_blocking_method(arg, *args, kwarg=kwarg, **kwargs))
                    return 5

                def object_blocking_method(self, arg, *args, kwarg=None, **kwargs):
                    __(sync_blocking_function())
                    __(print(arg, kwarg, args, kwargs))
                    return 5
        """
        )
        with self.assertAddsMessages(
            pylint.testutils.MessageTest(
                msg_id="blocking-call",
                node=calls[8],
                args=(
                    "Object.object_blocking_method -> sync_blocking_function -> barbican.secrets.get",
                ),
            ),
            ignore_position=True,
        ):
            for call in calls:
                self.checker.visit_call(call)
            self.checker.close()

    def test_check_threaded_call_not_blocking(self):
        calls = astroid.extract_node(
            """             
            def thread(func) -> Callable[..., Awaitable[Any]]:
                @functools.wraps(func)
                def wrap(*args, **kwargs):
                    loop = asyncio.get_event_loop()
                    current_context = copy_context()
                    return loop.run_in_executor(settings.executor, current_context.run, lambda: func(*args, **kwargs))

                return wrap

            def sync_blocking_function():
                barbican = ...
                barbican.secrets.get()   #@

            @thread
            def threaded_sync_function_not_blocking():
                sync_blocking_function()    #@

            async def async_function_with_threaded_not_blocking(neutron):
                threaded_sync_function_not_blocking(neutron, 5)   #@
        """
        )
        with self.assertNoMessages():
            for call in calls:
                self.checker.visit_call(call)
            self.checker.close()

    def test_check_blocking_call_names(self):
        calls = astroid.extract_node(
            """              
            class Object:     
                async def blocking_calls(self):
                    self.barbican().secrets.get()           #@          
                    self.cinder().volume_snapshots.list()           #@
                    self.glance().images.list()         #@
                    self.heat().resources.get()         #@
                    ironic.node.get()           #@
                    self.neutron().list_floating_ips()          #@
                    self.nova.servers.list()            #@
                    self.octavia().l7policy_show()          #@
                    get_session()           #@
                    session.commit()            #@
                    session.rollback()          #@
                    session.refresh()           #@
                    session.delete()            #@
                    session.query().filter().all()          #@
                    session.query().filter().first()            #@
                    session.query().filter().one()          #@
                    session.query().filter().one_or_none()          #@
                    os_session.auth.get_auth_ref()          #@
                    admin_keystone.access_rules.get()       #@
                    admin_keystone.application_credentials.create()       #@
                    admin_keystone.auth_manager.projects()       #@
                    admin_keystone.credentials.create() #@
                    admin_keystone.ec2.create() #@
                    admin_keystone.endpoint_filter.list_endpoints_for_project() #@
                    admin_keystone.endpoint_groups.create() #@
                    admin_keystone.endpoint_policy.create_policy_association_for_endpoint() #@
                    admin_keystone.endpoints.create() #@
                    admin_keystone.domain_configs.create() #@
                    admin_keystone.domains.create() #@
                    admin_keystone.federation.mappings.create() #@
                    admin_keystone.groups.create() #@
                    admin_keystone.limits.create() #@
                    admin_keystone.policies.create() #@
                    admin_keystone.projects.create() #@
                    admin_keystone.registered_limits.create() #@
                    admin_keystone.regions.create() #@
                    admin_keystone.role_assignments.list() #@
                    admin_keystone.roles.create() #@
                    admin_keystone.inference_rules.create() #@
                    admin_keystone.services.create() #@
                    admin_keystone.simple_cert.get_ca_certificates() #@
                    admin_keystone.tokens.revoke_token() #@
                    admin_keystone.trusts.create() #@
                    admin_keystone.users.find() #@
        """
        )
        messages = [
            pylint.testutils.MessageTest(
                msg_id="blocking-call", node=call, args=(helpers.get_call_name(call),)
            )
            for call in calls
        ]
        with self.assertAddsMessages(
            *messages,
            ignore_position=True,
        ):
            for call in calls:
                self.checker.visit_call(call)
            self.checker.close()

    def test_skip_function_names(self):
        calls = astroid.extract_node(
            """
            def sync_blocking_function(self):
                    self.barbican().secrets.get()           #@

            def delete_flow(self):
                sync_blocking_function()    #@

            async def another_async_func(self):
                delete_flow()    #@

            async def delete_flow_async(self):
                sync_blocking_function()    #@
                session.commit()    #@              
        """
        )
        with self.assertNoMessages():
            for call in calls:
                self.checker.visit_call(call)
            self.checker.close()

    def test_skip_module_names(self):
        for module_name in (
            "src.db.task",
            "src.db.tasks.ai",
            "src.db.task",
            "src.worker.task",
            "src.tests.db_fixtures",
            "src.tests.common.common",
        ):
            self.checker.linter.current_name = module_name
            call = astroid.extract_node(
                """                        
                async def async_blocking_function(self):
                    self.barbican().secrets.get()           #@
            """
            )
            with self.assertNoMessages():
                self.checker.visit_call(call)
                self.checker.close()
